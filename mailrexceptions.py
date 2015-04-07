class InvalidInputException(Exception):
    """
        Exception to be raised whenever the input specified for any of the requests is invalid
    """
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        """
            Initializes a new InvalidInputException
            
            Args:
                message (string) - Main error message that caused the exception to be raised
                status_code (int) - Status code to be returned when response is sent due to this exception being raised.
                                    By default this will be 400
                payload (dict) - Dictionary containing errors associated with the exception. Keys in the dictionary
                                 will be dependant on the exception condition and are not pre-specified
        """
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        """
            Returns a representation of the exception & associated errors as a dict
            
            Returns:
                dict - The key-value pairs in the dict contain information about the Exception that should be returned
                       to the user if a response is sent due to this exception being raised.
        """
        exception_dict = self.payload or {}
        exception_dict['message'] = self.message
        return exception_dict

class MailNotSentException(Exception):
    """
        Exception to be raised when a Mailer can't send the message
    """
    def __init__(self,message,status_code):
        """
            Initializes a new MailNotSentException
            
            Args:
                message (string) - Main error message that caused the exception to be raised
                status_code (int) - Status code to be returned when response is sent due to this exception being raised.
                                    By default this will be 400
        """
        Exception.__init__(self)
        self.message = message
        self.status_code = status_code