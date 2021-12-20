/**
 * This software was developed at the National Institute of Standards and Technology by employees of
 * the Federal Government in the course of their official duties. Pursuant to title 17 Section 105
 * of the United States Code this software is not subject to copyright protection and is in the
 * public domain. This is an experimental system. NIST assumes no responsibility whatsoever for its
 * use by other parties, and makes no guarantees, expressed or implied, about its quality,
 * reliability, or any other characteristic. We would appreciate acknowledgement if the software is
 * used. This software can be redistributed and/or modified freely provided that any derivative
 * works bear some notice that they are derived from it, and any modified versions bear some notice
 * that they have been modified.
 * @author: Deoyani Nandrekar-Heinis
 */
package gov.nist.oar.customizationapi.web;

import java.io.IOException;
import javax.servlet.http.HttpServletRequest;
import javax.validation.Valid;
import org.bson.Document;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
//import org.springframework.security.authentication.InternalAuthenticationServiceException;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClientException;

import gov.nist.oar.customizationapi.exceptions.CustomizationException;
import gov.nist.oar.customizationapi.exceptions.ErrorInfo;
import gov.nist.oar.customizationapi.exceptions.InvalidInputException;
import gov.nist.oar.customizationapi.exceptions.UnAuthorizedUserException;
import gov.nist.oar.customizationapi.repositories.EditorService;
//import gov.nist.oar.customizationapi.repositories.UpdateRepository;
import gov.nist.oar.customizationapi.service.ResourceNotFoundException;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;

/**
 * This is a webservice/restapi controller which gives options to access, update
 * and delete the record. There are four end points provided in this, each
 * dealing with specific tasks. In OAR project internal landing page for the edi
 * record is accessed using backed metadata. This metadata is a advanced POD
 * record called NERDm. In this api we are allowing the record to be modified by
 * authorized user. This webservice connects to backend MongoDB which holds the
 * record being edited. When the record is accessed for the first time, it is
 * fetched from backend metadata service. If it gets modified the updated record
 * is saved in this stagging database until finalzed Once it is finalized it is
 * pushed back to backend service to merge and send to review.
 * 
 * @author Deoyani Nandrekar-Heinis
 *
 */
@RestController
@Tag(description = "Api endpoints to access editable data, update changes to data, save in the backend", name = "Customization API")
@Validated
@CrossOrigin(origins = "*", allowedHeaders = "*")
@RequestMapping("/pdr/lp/editor/")
public class EditorController {
	private Logger logger = LoggerFactory.getLogger(EditorController.class);

	@Autowired
	private EditorService uRepo;

	/**
	 * Update the metadata, field or group of fileds allowed by the service. 
	 * 
	 * @param ediid  unique record id
	 * @param params subset of metadata modified in JSON format
	 * @return Updated record in JSON format
	 * @throws CustomizationException
	 * @throws InvalidInputException
	 */
	@RequestMapping(value = {
			"{ediid}" }, method = RequestMethod.PATCH, headers = "accept=application/json", produces = "application/json")
	@Operation(summary = "Cache Record Changes", description = "Resource returns a record if it is editable and user is authenticated.")
	public Document updateRecord(@PathVariable @Valid String ediid, @Valid @RequestBody String params)
			throws CustomizationException, InvalidInputException {

		logger.info("Update the given record: " + ediid);
		return uRepo.patchRecord(params, ediid);

	}

	/***
	 * Find the record in cache which is being edited by client
	 * 
	 * @param ediid Unique record identifier
	 * @return
	 * @throws CustomizationException
	 */
	@RequestMapping(value = { "{ediid}" }, method = RequestMethod.GET, produces = "application/json")
	@Operation(summary = "Access editable Record", description = "Resource returns a record if it is editable and user is authenticated.")
	public Document getRecord(@PathVariable @Valid String ediid) throws CustomizationException, ResourceNotFoundException {
		logger.info("Access the record to be edited by ediid " + ediid);
		return uRepo.getRecord(ediid);
	}

	/***
	 * Discard/delete the changes made from client/UI side, keeping the original record as it is. 
	 * 
	 * @param ediid Unique record identifier
	 * @return boolean true if successfully updated record.22
	 * @throws CustomizationException
	 */
	@RequestMapping(value = { "{ediid}" }, method = RequestMethod.DELETE, produces = "application/json" )
	@Operation(summary = "Access editable Record", description = "Resource returns a record if it is editable and user is authenticated.")
	public Document deleteChanges(@PathVariable @Valid String ediid) throws CustomizationException, ResourceNotFoundException {
		logger.info("Delete the changes made from client side of the record respresented by " + ediid);
		return uRepo.deleteRecordChanges(ediid);
	}
	/**
	 *  This exception is thrown only if there is an error in the service
	 * @param ex
	 * @param req
	 * @return
	 */
	@ExceptionHandler(CustomizationException.class)
	@ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
	public ErrorInfo handleCustomization(CustomizationException ex, HttpServletRequest req) {
		logger.error("There is an error in the service: " + req.getRequestURI() + "\n  " + ex.getMessage(), ex);
		return new ErrorInfo(req.getRequestURI(), 500, "Internal Server Error",req.getMethod());
	}

	/**
	 * Resource not found exception
	 * @param ex
	 * @param req
	 * @return
	 */
	@ExceptionHandler(ResourceNotFoundException.class)
	@ResponseStatus(HttpStatus.NOT_FOUND)
	public ErrorInfo handleStreamingError(ResourceNotFoundException ex, HttpServletRequest req) {
		logger.info("There is an error accessing requested record : " + req.getRequestURI() + "\n  " + ex.getMessage());
		return new ErrorInfo(req.getRequestURI(), 404, "Resource Not Found", req.getMethod());
	}

	/**
	 * Invalid input exception
	 * @param ex
	 * @param req
	 * @return
	 */
	@ExceptionHandler(InvalidInputException.class)
	@ResponseStatus(HttpStatus.BAD_REQUEST)
	public ErrorInfo handleStreamingError(InvalidInputException ex, HttpServletRequest req) {
		logger.info("There is an error processing input data: " + req.getRequestURI() + "\n  " + ex.getMessage());
		return new ErrorInfo(req.getRequestURI(), 400, "Invalid input error", req.getMethod());
	}

	/**
	 * Internal server error
	 * @param ex
	 * @param req
	 * @return
	 */
	@ExceptionHandler(IOException.class)
	@ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
	public ErrorInfo handleStreamingError(CustomizationException ex, HttpServletRequest req) {
		logger.info("There is an error accessing data: " + req.getRequestURI() + "\n  " + ex.getMessage());
		return new ErrorInfo(req.getRequestURI(), 500, "Internal Server Error", req.getMethod());
	}

	/**
	 * 
	 * @param ex
	 * @param req
	 * @return
	 */
	@ExceptionHandler(RuntimeException.class)
	@ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)

	public ErrorInfo handleStreamingError(RuntimeException ex, HttpServletRequest req) {
		logger.error("Unexpected failure during request: " + req.getRequestURI() + "\n  " + ex.getMessage(), ex);
		return new ErrorInfo(req.getRequestURI(), 500, "Unexpected Server Error",req.getMethod());
	}

	/**
	 * If backend server , IDP or metadata server is not working it wont authorized
	 * the user but it will throw an exception.
	 * 
	 * @param ex
	 * @param req
	 * @return
	 */
	@ExceptionHandler(RestClientException.class)
	@ResponseStatus(HttpStatus.BAD_GATEWAY)
	public ErrorInfo handleRestClientError(RuntimeException ex, HttpServletRequest req) {
		logger.error("Unexpected failure during request: " + req.getRequestURI() + "\n  " + ex.getMessage(), ex);
		return new ErrorInfo(req.getRequestURI(), 502, "Can not connect to backend server",req.getMethod());
	}

	

	/**
	 * Exception handling if user is not authorized
	 * 
	 * @param ex
	 * @param req
	 * @return
	 */
	@ExceptionHandler(UnAuthorizedUserException.class)
	@ResponseStatus(HttpStatus.UNAUTHORIZED)
	public ErrorInfo handleStreamingError(UnAuthorizedUserException ex, HttpServletRequest req) {
		logger.info("There user requesting edit access is not authorized : " + req.getRequestURI() + "\n  "
				+ ex.getMessage());
		return new ErrorInfo(req.getRequestURI(), 401, "UnauthroizedUser", req.getMethod());
	}
//	/**
//	 * Handles internal authentication service exception if user is not authorized
//	 * or token is expired
//	 * 
//	 * @param ex
//	 * @param req
//	 * @return
//	 */
//	@ExceptionHandler(InternalAuthenticationServiceException.class)
//	@ResponseStatus(HttpStatus.UNAUTHORIZED)
//	public ErrorInfo handleRestClientError(InternalAuthenticationServiceException ex, HttpServletRequest req) {
//		logger.error("Unauthorized user or token : " + req.getRequestURI() + "\n  " + ex.getMessage(), ex);
//		return new ErrorInfo(req.getRequestURI(), 401, "Untauthorized user or token.");
//	}
}
