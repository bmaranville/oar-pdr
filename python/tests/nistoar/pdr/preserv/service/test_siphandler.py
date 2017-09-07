import os, pdb, sys, logging
import unittest as test

from nistoar.testing import *
from nistoar.pdr.preserv.service import siphandler as sip
from nistoar.pdr.preserv.service import status

# datadir = nistoar/preserv/data
datadir = os.path.join( os.path.dirname(os.path.dirname(__file__)), "data" )

loghdlr = None
rootlog = None
def setUpModule():
    ensure_tmpdir()
    rootlog = logging.getLogger()
    loghdlr = logging.FileHandler(os.path.join(tmpdir(),"test_siphandler.log"))
    loghdlr.setLevel(logging.INFO)
    rootlog.addHandler(loghdlr)

def tearDownModule():
    global loghdlr
    if loghdlr:
        if rootlog:
            rootlog.removeLog(loghdlr)
        loghdlr = None
    rmtmpdir()

class TestMIDASSIPHandler(test.TestCase):

    sipdata = os.path.join(datadir, "midassip", "review", "1491")
    midasid = '3A1EE2F169DD3B8CE0531A570681DB5D1491'

    def setUp(self):
        self.tf = Tempfiles()
        self.troot = self.tf.mkdir("siphandler")
        self.revdir = os.path.join(self.troot, "review")
        os.mkdir(self.revdir)
        self.workdir = os.path.join(self.troot, "working")
        # os.mkdir(self.workdir)
        self.stagedir = os.path.join(self.troot, "staging")
        # os.mkdir(self.stagedir)
        self.mdserv = os.path.join(self.troot, "mdserv")
        os.mkdir(self.mdserv)
        self.store = os.path.join(self.troot, "store")
        os.mkdir(self.store)
        self.statusdir = os.path.join(self.troot, "status")
        os.mkdir(self.statusdir)

        shutil.copytree(self.sipdata, os.path.join(self.revdir, "1491"))

        self.config = {
            "working_dir": self.workdir,
            "store_dir": self.store,
            "staging_dir": self.stagedir,
            "review_dir":  self.revdir,
            "mdbag_dir":   self.mdserv,
            "status_manager": { "cachedir": self.statusdir },
            "logdir": self.workdir,
            "bagparent_dir": "_preserv",
            "bagger": { 'relative_to_indir': True }
        }
        
        self.sip = sip.MIDASSIPHandler(self.midasid, self.config)

    def tearDown(self):
        self.sip = None
        self.tf.clean()

    def test_ctor(self):
        self.assertTrue(self.sip.bagger)
        self.assertTrue(os.path.exists(self.workdir))
        self.assertTrue(os.path.exists(self.stagedir))
        self.assertTrue(os.path.exists(self.mdserv))

        self.assertTrue(isinstance(self.sip.status, dict))
        self.assertEqual(self.sip.state, status.FORGOTTEN)

    def test_set_state(self):
        self.assertEqual(self.sip.state, status.FORGOTTEN)
        self.sip.set_state(status.SUCCESSFUL, "Yeah!")
        self.assertEqual(self.sip.state, status.SUCCESSFUL)
        self.assertEqual(self.sip._status.message, "Yeah!")

    def test_isready(self):
        self.assertEqual(self.sip.state, status.FORGOTTEN)
        self.assertTrue(self.sip.isready())
        self.assertEqual(self.sip.state, status.READY)

    def test_bagit(self):
        self.assertEqual(self.sip.state, status.FORGOTTEN)
        self.sip.bagit()
        self.assertTrue(os.path.exists(os.path.join(self.store,
                                                self.midasid+".mbag0_2-0.zip")))
        self.assertTrue(os.path.exists(os.path.join(self.store,
                                         self.midasid+".mbag0_2-0.zip.sha256")))
        self.assertEqual(self.sip.state, status.SUCCESSFUL)
        

if __name__ == '__main__':
    test.main()
