"""
This bagger submodule provides functions for preparing an update to a previously
preserved collection.  This includes a service client for retrieving previous
head bags from cache or long-term storage.  
"""
import os, shutil, json, logging, re, time
from abc import ABCMeta, abstractmethod, abstractproperty
from collections import OrderedDict
from zipfile import ZipFile
from datetime import datetime

from .base import sys as _sys
from .. import (ConfigurationException, StateException, CorruptedBagError,
                NERDError)
from . import utils as bagutils
from ...config import merge_config
from ...describe import rmm
from ... import distrib
from ...exceptions import IDNotFound
from ... import utils
from ..bagit.builder import BagBuilder, ARK_NAAN
from ..bagit.bag import NISTBag
from ... import PDR_PUBLIC_SERVER

PDR_SERVER = PDR_PUBLIC_SERVER
deflog = logging.getLogger(_sys.system_abbrev).getChild(_sys.subsystem_abbrev)
ARK_PFX = "ark:/{0}/".format(ARK_NAAN)

class HeadBagCacher(object):
    """
    a helper class that manages serialized head bags in a local cache.
    """
    def __init__(self, distrib_service, cachedir, infodir=None):
        """
        set up the cache
        :param RESTServiceClient distrib_service:  the distribution service 
                               to use to pull in head bags from.
        :param str cachedir:   the path to the directory where bags will be 
                               cached.
        :param str infodir:    the path to the directory where bag metadata 
                               will be stored.  If not provided, a subdirectory
                               of cachedir, "_info", will be used.
        """
        self.distsvc = distrib_service
        self.cachedir = cachedir
        if not infodir:
            infodir = os.path.join(self.cachedir, "_info")
        self.infodir = infodir

        if not os.path.exists(self.cachedir):
            os.mkdir(self.cachedir)
        if not os.path.isdir(self.cachedir):
            raise StateException("HeadBagCacher: not a directory: "+
                                 self.cachedir)
        if not os.path.exists(self.infodir):
            os.mkdir(self.infodir)
        if not os.path.isdir(self.infodir):
            raise StateException("HeadBagCacher: not a directory: "+
                                 self.cachedir)
        

    def cache_headbag(self, aipid, version=None, confirm=True):
        """
        ensure a copy of the serialized head bag in the cache
        :rtype: str giving the path to the cached, serialized head bag or 
                None if no such bag exists.  
        """
        bagcli = distrib.BagDistribClient(aipid, self.distsvc)

        hinfo = None
        if version and version != 'latest':
            # map id,version to bagfile using our local cache
            info = self._recall_head_info(aipid)
            if version in info and 'name' in info[version]:
                hinfo = info[version]

        if not hinfo:
            # map id,version to bagfile using the remote service
            try:
                hinfo = bagcli.describe_head_for_version(version)
            except distrib.DistribResourceNotFound as ex:
                return None

            # cache the info locally
            if not version or version == 'latest':
                version = hinfo['sinceVersion']
            self._cache_head_info(aipid, version, hinfo)

        # look for bag in cache; if not there, fetch a copy
        bagfile = os.path.join(self.cachedir, hinfo['name'])
        if not os.path.exists(bagfile):
            bagcli.save_bag(hinfo['name'], self.cachedir)
        if confirm:
            self.confirm_bagfile(hinfo)

        return bagfile

    def confirm_bagfile(self, baginfo, purge_on_error=True):
        """
        Make sure the cached bag described by bag metadata was transfered
        correctly by checking it checksum.  
        :raise CorruptedBagError: if an error was detected.
        """
        bagfile = os.path.join(self.cachedir, baginfo['name'])
        try:
            if utils.checksum_of(bagfile) != baginfo['checksum']['hash']:
                if purge_on_error:
                    # bag file looks corrupted; purge it from the cache
                    self._clear_from_cache(bagfile, baginfo)
                    
                raise CorruptedBagError(bagfile, bagfile+": checksum failure")
        except OSError as ex:
            if purge_on_error:
                self._clear_from_cache(bagfile, baginfo)
                
            raise CorruptedBagError(bagfile, "Failure reading bag file: " +
                                    bagfile + ": " + str(ex), cause=ex)

    def _clear_from_cache(self, bagfile, baginfo=None):
        if os.path.exists(bagfile):
            os.remove(bagfile)
        if baginfo:
            info = self._recall_head_info(baginfo['aipid'])
            if baginfo['sinceVersion'] in info:
                del info[baginfo['sinceVersion']]
                self._save_head_info(baginfo['aipid'], info)

    def _cache_head_info(self, aipid, version, info):
        out = self._recall_head_info(aipid)
        out[version] = info
        self._save_head_info(aipid, out)

    def _save_head_info(self, aipid, info):
        with open(self._head_info_file(aipid), 'w') as fd:
            json.dump(info, fd, indent=2)

    def _head_info_file(self, aipid):
        return os.path.join(self.infodir, aipid)

    def _recall_head_info(self, aipid):
        hif = self._head_info_file(aipid)
        if not os.path.exists(hif):
            return OrderedDict()
        with open(hif) as fd:
            return json.load(fd, object_pairs_hook=OrderedDict)
            

class UpdatePrepService(object):
    """
    a factory class that creates UpdatePrepper instances
    """
    def __init__(self, config, bgrmdf=None):
        self.cfg = config

        self.sercache = self.cfg.get('headbag_cache')
        if not self.sercache:
            raise ConfigurationException("UpdatePrepService: Missing property: "+
                                         "headbag_cache")
        self.storedir = self.cfg.get('store_dir')
        scfg = self.cfg.get('distrib_service', {})
        self.distsvc = distrib.RESTServiceClient(scfg.get('service_endpoint'))
        self.cacher = HeadBagCacher(self.distsvc, self.sercache)

        self.mdsvc = None
        scfg = self.cfg.get('metadata_service', {})
        if scfg.get('service_endpoint'):
            self.mdsvc  = rmm.MetadataClient(scfg.get('service_endpoint'))

        self._bgrmdf = bgrmdf

    def prepper_for(self, aipid, version=None, replaces=None, log=None):
        """
        return an UpdatePrepper instance for the given dataset identifier
        """
        return UpdatePrepper(aipid, self.cfg, self.cacher, self.mdsvc,
                             self.storedir, version, replaces, log, self._bgrmdf)


class UpdatePrepper(object):
    """
    a class that restores the latest head bag of a previously preserved dataset
    to disk and prepares it for access and possible update by the PDR publishing 
    system.  
    """
    PREPRMD_FILENAME = "__bagger-prepper.json"

    def __init__(self, aipid, config, headcacher, pubmdclient, storedir=None,
                 version=None, replaces=None, log=None, bgrmdf=None):
        """
        create the prepper for the given dataset identifier.  

        This is not intended to be instantiated directly by the user; use
        the UpdatePrepService.prepper_for() factory method. 
        """
        self._aipid = aipid
        self._prevaipid = replaces
        if not self._prevaipid:
            self._prevaipid = aipid
        self.cacher = headcacher
        self.storedir = storedir
        self.version = version
        self.mdcli = pubmdclient
        self.mdcache = os.path.join(self.cacher.cachedir, "_nerd")
        if not os.path.exists(self.mdcache):
            os.mkdir(self.mdcache)
        if not os.path.isdir(self.mdcache):
            raise StateException("UpdatePrepper: not a directory: "+self.mdcache)

        if not log:
            log = deflog.getChild(self.aipid[:8]+'...')
        self.log = log

        if not bgrmdf:
            bgrmdf = os.path.join("metadata", self.PREPRMD_FILENAME)
        self._bgrmdf = bgrmdf

    @property
    def aipid(self):
        """
        The AIP identifier for the dataset that this UpdatePrepper will look for
        """
        return self._aipid

    def cache_headbag(self):
        """
        ensure a copy of the serialized head bag in the read-only cache
        :rtype: str giving the path to the cached, serialized head bag or 
                None if no such bag exists.  
        """
        out = self._cache_headbag_for(self.aipid)
        if not out and self._prevaipid != self.aipid:
            out = self._cache_headbag_for(self._prevaipid, None) # get only latest version
        return out

    def _cache_headbag_for(self, aipid, version=None):
        try:
            return self.cacher.cache_headbag(aipid, version)
        except CorruptedBagError as ex:
            # try again (now that the cache is clean)
            return self.cacher.cache_headbag(aipid, version)

    def cache_nerdm_rec(self, shallow=False):
        """
        ensure a cached copy of the latest NERDm record from the repository.
        This is called for datasets that are in the PDL but have not gone 
        through the preservation service.  
        :param str shallow:  if True, cache the ancestor record if this is an unpublished AIP
                             derived from a published one.  (default: False)
        :rtype: str giving the path to the cached NERDm record, or
                None if no such bag exists.  
        """
        out = self._cache_nerdm_rec_for(self.aipid)
        if not shallow and not out and self._prevaipid != self.aipid:
            out = self._cache_nerdm_rec_for(self._prevaipid) # get only latest version
        return out

    def _cache_nerdm_rec_for(self, aipid):
        out = os.path.join(self.mdcache, aipid+".json")
        if not os.path.exists(out):
            if not self.mdcli:
                # not configured to consult repository
                return None
            try:
                data = self.mdcli.describe(aipid)
                with open(out, 'w') as fd:
                    json.dump(data, fd, indent=2)
            except IDNotFound as ex:
                return None
        return out

    def find_bag_in_store(self, aipid, version):
        """
        look for a bag for a particular version of the AIP with the given ID
        in the bag storage directory.  (This is the directory where AIP bags 
        are copied to for long-term storage.)
        """
        if not self.storedir:
            return None

        foraip = [f for f in os.listdir(self.storedir)
                    if f.startswith(aipid+'.') and not f.endswith('.sha256')]

        foraip = bagutils.select_version(foraip, version)
        if len(foraip) == 0:
            return None

        return os.path.join(self.storedir, bagutils.find_latest_head_bag(foraip))

    def aip_exists(self, deep=False):
        """
        return true if a previously ingested AIP with the current ID exists in 
        the repository.  By default, this function only considered the AIP ID attached to 
        this prepper: if this AIP is derived from a previously published AIP with a different ID, 
        this function returns False.  If deep=True, then this case will return True.  
        """
        return self.cache_nerdm_rec(shallow=not deep) is not None
        
    def _unpack_bag_as(self, bagfile, destbag):
        destdir = os.path.dirname(destbag)

        if bagfile.endswith('.zip'):
            root = self._unpack_zip_into(bagfile, destdir)
        else:
            raise StateException("Don't know how to unpack serialized bag: "+
                                 os.path.basename(bagfile))

        tmpname = os.path.join(destdir, root)
        if not os.path.isdir(tmpname):
            raise RuntimeException("Apparent bag unpack failure; root "+
                                   "not created: "+tmpname)
        os.rename(tmpname, destbag)
        
    def _unpack_zip_into(self, bagfile, destdir):
        if not os.path.exists(destdir):
            raise StateException("Bag destination directory not found: "+destdir)
                                 
        # this coder gratefully drew on the example by Jawaad Ahmad (jia103) at
        # https://stackoverflow.com/questions/9813243/extract-files-from-zip-file-and-retain-mod-date-python-2-7-1-on-windows-7
        # for restoring the content's original data-time stamps.

        dirs = {}
        with ZipFile(bagfile, 'r') as zip:
            contents = zip.namelist()
            root = None
            for name in contents:
                parts = name.split("/")
                root = parts[0]
                if root:
                    break

            if not root:
                raise StateException("Bag appears to be empty: "+bagfile)

            for entry in zip.infolist():
                zip.extract(entry, destdir)
                extracted = os.path.join(destdir, entry.filename)
                date_time = time.mktime(entry.date_time + (0, 0, -1))

                if os.path.isdir(extracted):
                    dirs[extracted] = date_time
                else:
                    os.utime(extracted, (date_time, date_time))

        for name in dirs:
            os.utime(name, (dirs[name], dirs[name]))

        return root


    def create_new_update(self, destbag):
        """
        create an updatable metadata bag for the purposes of creating a new 
        version of the dataset.   If this dataset has been through the 
        preservation service before, it will be built from the latest headbag;
        otherwise, it will be created from its latest public NERDm record.  

        :param str destbag:  the full path to the root directory of the metadata 
                             bag to create
        """
        mdbag = destbag
        if os.path.exists(mdbag):
            self.log.warning("Removing existing metadata bag for id="+self.aipid+
                             "\n   (may indicate earlier failure)")
            shutil.rmtree(mdbag)

        latest_nerd = self.cache_nerdm_rec()
        if not latest_nerd:
            self.log.info("ID not published previously; will start afresh")
            return False
        nerd = utils.read_nerd(latest_nerd)
        latest_aipid = re.sub(r'^ark:/\d+/', '', nerd.get("ediid", self.aipid))
        version = self.version
        if not version:
            version = nerd.get('version', '0')

        if latest_aipid != self.aipid:
            self.log.info("Note: previously published dataset being revised with new EDI ID")
            prev_mdbag = os.path.join(os.path.dirname(mdbag), latest_aipid)
            if os.path.exists(prev_mdbag):
                self.log.warning("Removing existing metadata bag for previous id="+latest_aipid)
                shutil.rmtree(prev_mdbag)

        # This has been published before; look for a head bag in the store dir
        latest_headbag = self.find_bag_in_store(latest_aipid, version)
        if not latest_headbag:
            # store dir came up empty; try the distribution service
            latest_headbag = self.cache_headbag()

        if latest_headbag:
            fmt = "Preparing update based on previous head preservation bag (%s)"
            self.log.info(fmt, os.path.basename(latest_headbag)) 
            self.create_from_headbag(latest_headbag, mdbag,
                                     (self.aipid != latest_aipid and self.aipid) or None)
            if self.aipid != latest_aipid:
                self._baggermd_update({"replacedEDI": self._prevaipid}, mdbag)
            return True

        # This dataset was "published" without a preservation bag
        self.log.info("No previous bag available; preparing based on " +
                      "existing published NERDm record")
        self.create_from_nerdm(latest_nerd, mdbag, 
                               (self.aipid != latest_aipid and self.aipid) or None)
        if self.aipid != latest_aipid:
            self._baggermd_update({"replacedEDI": self._prevaipid}, mdbag)
            
        return True

    def _baggermd_replace(self, mdata, inbag):
        utils.write_json(mdata, os.path.join(inbag, self._bgrmdf))
    def _baggermd_update(self, mdata, inbag):
        bgrmdf = os.path.join(inbag, self._bgrmdf)
        if os.path.exists(bgrmdf):
            md = utils.read_json()
        else:
            md = OrderedDict()
        md = merge_config(mdata, md)
        self._baggermd_replace(md, inbag)
        

    def create_from_headbag(self, headbag, mdbag, foraip=None):
        """
        create an updatable metadata bag from the latest headbag for
        the purposes of creating a new version.

        :param str headbag:  the path to an existing head bag to convert
        :param str mdbag:    the destination metadata bag to create (and 
                             thus should not yet exist).
        :param str foraip:   the AIP-ID that the mdbag metadata bag is for;
                             if None, this defaults to that assigned to headbag
        """
        if os.path.exists(mdbag):
            raise StateException("UpdatePrepper: metadata bag already exists "+
                                 "for id=" + self.aipid + ": " + mdbag)
        parent = os.path.dirname(mdbag)
        if not os.path.isdir(parent):
            raise StateException("metadata bag working space does not exist: "+
                                 parent)

        if os.path.isdir(headbag):
            # unserialized bag
            shutil.copytree(headbag, mdbag)
            
        elif not os.path.isfile(headbag):
            raise ValueError("UpdatePrepper: head bag does not exist: "+headbag)

        else:
            # serialized bag file
            self._unpack_bag_as(headbag, mdbag)

        # save the the bag-info.txt as deprecated-info.txt for later use
        mbdir = os.path.join(mdbag, "multibag")
        if not os.path.isdir(mbdir):
            os.mkdir(mbdir)
        shutil.copyfile(os.path.join(mdbag,"bag-info.txt"),
                        os.path.join(mbdir,"deprecated-info.txt"))

        # now remove certain bits that will get updated later
        datadir = os.path.join(mdbag, "data")
        if os.path.exists(datadir):
            shutil.rmtree(datadir)
        os.mkdir(datadir)

        for file in "bagit.txt bag-info.txt manifest-sha256.txt tagmanifest-sha256.txt about.txt".split():
            file = os.path.join(mdbag, file)
            if os.path.exists(file):
                os.remove(file)

        # update the metadata to the latest NERDm schema version
        # (this assumes forward compatibility).
        bag = NISTBag(mdbag)
        nerdm = bagutils.update_nerdm_schema(bag.nerdm_record())
        if not nerdm.get('@id'):
            raise StateException("Bag {0}: missing @id"
                                 .format(os.path.basename(mdbag)))

        if foraip:
            # update the EDI-ID if this represents a change in the EDI-ID
            oldediid = nerdm['ediid']
            foraip = re.sub(r'^ark:/\d+/','',foraip)
            ediid = foraip
            if len(ediid) < 30:
                ediid = ARK_PFX + ediid
            nerdm['ediid'] = ediid

            if 'doi' in nerdm:
                if 'replaces' not in nerdm:
                    nerdm['replaces'] = []
                now = datetime.fromtimestamp(time.time()).isoformat()
                nerdm['replaces'].append(OrderedDict([
                    ("@id", nerdm['doi']),
                    ("ediid", oldediid),
                    ("issued", nerdm.get('issued', nerdm.get('modified', now)))
                ]))
                if 'version' in nerdm:
                    nerdm['replaces'][-1]['version'] = nerdm['version']
                if 'title' in nerdm:
                    nerdm['replaces'][-1]['title'] = nerdm['title']

        bag = BagBuilder(parent, os.path.basename(mdbag), {'validate_id': False},
                         nerdm.get('@id'), logger=self.log)
        try:
            bag.add_res_nerd(nerdm, savefilemd=True)
        finally:
            bag.disconnect_logfile() # disconnect internal log file

        # finally set the version to a value appropriate for an update in
        # progress
        self.update_version_for_edit(mdbag)

    def create_from_nerdm(self, nerdfile, mdbag, foraip=None):
        """
        create an updatable metadata bag from the latest NERDm record for
        the purposes of creating a new version of the dataset.

        :param str nerdfile:  the path to a cached NERDm record
        :param str mdbag:     the destination metadata bag to create (and 
                              thus should not yet exist).
        """
        if os.path.exists(mdbag):
            raise StateException("UpdatePrepper: metadata bag already exists "+
                                 "for id=" + self.aipid + ": "+mdbag)
        parent = os.path.dirname(mdbag)
        bagname = os.path.basename(mdbag)
        if not os.path.isdir(parent):
            raise StateException("metadata bag working space does not exist: "+
                                 parent)

        if not os.path.exists(nerdfile):
            raise ValueError("Cached NERDm record not found: " + nerdfile)

        nerd = utils.read_nerd(nerdfile)
        if not '@id' in nerd:
            raise NERDError("Missing @id from NERD rec, "+nerdfile)

        # update the schema version to the latest supported version
        # (this assumes forward compatibility).
        bagutils.update_nerdm_schema(nerd)
        
        if foraip:
            # update the EDI-ID if this represents a change in the EDI-ID
            oldediid = nerdm['ediid']
            foraip = re.sub(r'^ark:/\d+/','',foraip)
            ediid = foraip
            if len(ediid) < 30:
                ediid = ARK_PFX + ediid
            nerdm['ediid'] = ediid

            if 'doi' in nerdm:
                if 'replaces' not in nerdm:
                    nerdm['replaces'] = []
                now = datetime.fromtimestamp(time.time()).isoformat()
                nerdm['replaces'] = OrderedDict([
                    ("@id", nerdm['doi']),
                    ("ediid", oldediid),
                    ("issued", nerdm.get('issued', nerdm.get('modified', now)))
                ])

        bldr = BagBuilder(parent, bagname, {'validate_id': False},
                          nerd['@id'], logger=self.log)
        try:
            bldr.add_res_nerd(nerd, savefilemd=True)
        finally:
            bldr.disconnect_logfile() # disconnect internal log file

        # update the version appropriate for edit mode
        self.update_version_for_edit(bldr.bagdir)

    def latest_version(self, source="repo"):
        """
        return the version label for the latest known version of the dataset.  The 
        choice for the source parameter can be chosen with consideration of the 
        current state of the dataset update or preservation process and performance.  
        :param str source:  a label indicating the method that should be used 
                            to determine the version, one of "repo" (query the 
                            repository's public metadata service), "bag-store" 
                            (the long-term bag storage directory), "bag-cache" 
                            (the bag-staging directory), "nerdm-cache"
                            (the local nerdm metadata cache).  "repo" is generally
                            considered most definitive but least performant.
        :rtype str:  the version string of the last known version.  "0" is returned if 
                     no previous version can be found/determined.
        """
        if not isinstance(source, (list, tuple)):
            source = [source]
        out = "0"
        for src in source:
            if src == "repo":
                out = self._latest_version_from_repo()
            elif src == "bag-store":
                if self.storedir:
                    out = self._latest_version_from_dir(self.storedir)
            elif src == "bag-cache":
                out = self._latest_version_from_dir(self.cacher.cachedir)
            elif src == "nerdm-cache":
                out = self._latest_version_from_nerdcache()
            else:
                raise ValueError("latest_version(): Unrecognized source label: "+str(src))
            if out != "0":
                return out
        return out

    def _latest_version_from_repo(self):
        latest_nerd = self.cache_nerdm_rec()
        if not latest_nerd:
            return "0"
        return self._latest_version_from_nerdmfile(latest_nerd)

    def _latest_version_from_nerdcache(self):
        nerdf = os.path.join(self.mdcache, self.aipid+".json")
        if not os.path.exists(nerdf) and self._prevaipid:
            nerdf = os.path.join(self.mdcache, self._prevaipid+".json")
        return self._latest_version_from_nerdmfile(nerdf)

    def _latest_version_from_dir(self, bagparent):
        foraip = [f for f in os.listdir(bagparent)
                    if f.startswith(self.aipid+'.') and
                       not f.endswith('.sha256')        ]
        if not foraip and self._prevaipid and self._prevaipid != self.aipid:
            foraip = [f for f in os.listdir(bagparent)
                        if f.startswith(self._prevaipid+'.') and
                           not f.endswith('.sha256')        ]
        if not foraip:
            return "0"
        latest = bagutils.find_latest_head_bag(foraip)

        version = re.sub(r'_', '.', bagutils.parse_bag_name(latest)[1])
        if not version:
            version = "1.0.0"
        return version

    def _latest_version_from_nerdmfile(self, nerdfile):
        if not os.path.exists(nerdfile):
            return "0"
        nerd = utils.read_nerd(nerdfile)
        return nerd.get('version', '0')
        
        
        

    def update_version_for_edit(self, bagdir):
        """
        update the version metadatum to something appropriate for edit mode.
        This will get updated according to policy as needed later.
        """
        bag = NISTBag(bagdir)
        mdata = bag.nerd_metadata_for('', merge_annots=True)
        oldvers = mdata.get('version', "1.0.0")
        relhist = mdata.get('releaseHistory')
        if relhist is None:
            relhist = OrderedDict([("@id", mdata['@id'] + ".rel"), ("@type", ["nrdr:ReleaseHistory"])])
            relhist['hasRelease'] = mdata.get('versionHistory', [])
        pdrid = re.sub(r'v\d+(_\d+)*$', '', mdata['@id'])

        edit_vers = self.make_edit_version(oldvers)
        self.log.debug('Setting edit version to "%s"', edit_vers)

        annotf = bag.annotations_file_for('')
        if os.path.exists(annotf):
            adata = utils.read_nerd(annotf)
        else:
            adata = OrderedDict()
        adata['version'] = edit_vers

        if oldvers != edit_vers and ('issued' in mdata or 'modified' in mdata) \
           and not any([h['version'] == oldvers] for h in relhist['hasRelease']):
            issued = ('modified' in mdata and mdata['modified']) or \
                     mdata['issued']
            relhist['hasRelease'].append(OrderedDict([
                ('version', oldvers),
                ('issued', issued),
                ('@id', mdata['@id'] + ".v" + re.sub(r'\.','_',oldvers)),
                ('location', 'https://'+PDR_SERVER+'/od/id/'+
                             mdata['@id']+'.v'+re.sub(r'\.','_', oldvers))
            ]))
            if oldvers == "1.0.0" or oldvers == "1.0" or oldvers == "1":
                relhist['hasRelease'][-1]['description'] = 'initial release'
            adata['releaseHistory'] = relhist
        
        utils.write_json(adata, annotf)
        
    def make_edit_version(self, prev_vers):
        return prev_vers + "+ (in edit)"
        
    def update_multibag_info(self, headbag, destbag):
        """
        copy the multibag info found in a specified head bag to a destination bag.  
        The multibag subdirectory in the destination bag may exist prior to calling 
        this function; only those files within with the same name as in the source 
        head bag will be overwritten.
        """
        if not os.path.exists(destbag):
            raise OSError(errno.EEXIST, os.strerror(errno.EEXIST), destbag)
        mbdir = os.path.join(destbag, "multibag")
        if not os.path.exists(mbdir):
            os.mkdir(mbdir)

        if os.path.isdir(headbag):
            # unserialized bag

            # copy the headbag's bag-info.txt as a deprecated one
            baginfo = os.path.join(headbag, "bag-info.txt")
            if os.path.isfile(baginfo):
                shutil.copy(baginfo, os.path.join(mbdir, "deprecated-info.txt"))

            # copy contents of the source multibag sub-directory
            hmbdir = os.path.join(headbag, "multibag")+os.sep
            for root, dirs, files in os.walk(hmbdir):
                relroot = root[len(hmbdir):]
                for d in dirs:
                    dest = os.path.join(mbdir, relroot, d)
                    if not os.path.isdir(dest):
                        os.mkdir(dest)
                for f in files:
                    shutil.copy(os.path.join(root, f), os.path.join(mbdir, relroot, f))
            
        elif not os.path.isfile(headbag):
            raise ValueError("UpdatePrepper: head bag does not exist: "+headbag)

        else:
            # serialized bag file
            # self._unpack_bag_as(headbag, mdbag)
            if not headbag.endswith('.zip'):
                raise StateException("Don't know how to unpack serialized bag: "+
                                     os.path.basename(headbag))
            with ZipFile(headbag, 'r') as zip:
                mbfiles = [f for f in zip.namelist() if '/multibag/' in f]
                if len(mbfiles) <= 0:
                    raise StateException("No multibag files found in headbag: "+
                                         os.path.basename(headbag))
                srcmbd = re.sub(os.sep+r'.*$', '', mbfiles[0])
                baginfo = "/".join([srcmbd, "bag-info.txt"])
                srcmbd += '/multibag/'

                for entry in zip.infolist():
                    if entry.filename == baginfo:
                        # copy the headbag's bag-info.txt as a deprecated-info.txt
                        entry.filename = "deprecated-info.txt"
                        zip.extract(entry, mbdir)
                        
                    elif entry.filename.startswith(srcmbd):
                        # copy the contents of the multibag subdirectory
                        # adjust the entry name so that we can send the file directly
                        # to the output multibag directory
                        entry.filename = entry.filename[len(srcmbd):]
                        if not entry.filename or entry.filename == "deprecated-info.txt":
                            continue
                        zip.extract(entry, mbdir)
        
    def set_multibag_info(self, destbag):
        """
        set or update the multibag info in a target bag with from the latest, previously
        published headbag for the dataset.  If none exist, the target bag is unchanged.  
        """
        latest_nerd = self.cache_nerdm_rec()
        if not latest_nerd:
            self.log.info("ID not published previously; will start afresh")
            return False
        nerd = utils.read_nerd(latest_nerd)
        latest_aipid = re.sub(r'^ark:/\d+/', '', nerd.get("ediid", self.aipid))
        version = self.version
        if not version:
            version = nerd.get('version', '0')

        # This has been published before; look for a head bag in the store dir
        latest_headbag = self.find_bag_in_store(latest_aipid, version)
        if not latest_headbag:
            # store dir came up empty; try the distribution service
            latest_headbag = self.cache_headbag()

        if not latest_headbag:
            # This dataset was "published" without a preservation bag
            self.log.info("No previous bag available; multibag info not initialized.")
            return False
        
        fmt = "Updating multibag info from previous head preservation bag (%s)"
        self.log.info(fmt, os.path.basename(latest_headbag))
        self.update_multibag_info(latest_headbag, destbag)
        return True

        
                    
                    
        
                             

        

