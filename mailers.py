from email import utils
from mailrexceptions import MailNotSentException
from random import shuffle
from requests.exceptions import ConnectTimeout
from rq import get_current_job
import abc
import config
import datetime
import json
import re
import requests
import time

class Mailer(object):
    """
        Base class for all classes that will implement the mail functionality.
    """
    __metaclass__ = abc.ABCMeta
    
    @abc.abstractmethod
    def send_message(self, **params):
        """
            Sends message to as per the parameters specified.

            Args:
                to (list) - List of emails to send the message to
                from_email (str) - Email to send the message on behalf of
                subject (str) - Subject of the message
                text (str) - Main text that should go in the body of the message
                cc (list) - Optional; list of emails to send the message to, with the 'cc' header
                bcc (list) - Optional; list of emails to send the message to, with the 'bcc' header

                All email fields are as specified in RFC-822

            Returns:
                list - Each element in the list is a dict with two properties:
                            -- ID of the message sent (which is provided by the underlying email service provider)
                            -- Email address to which the email was sent.
                        The list contains one dict for each entry in the 'to','cc' and 'bcc' fields.
        """
        #Each of these dicts is called as a 'message_info' for that message in code.
        pass

    @abc.abstractmethod
    def get_message_status(self,message_info):
        """
            Given the message_info for a message (i.e. email address of the message & the ID) this method
            returns the status of the request made for that message, by polling the email service provider
            that made the request for it.

            Args:
                message_info (dict) - Contains two fields 
                                        -- 'email', the email address to which the message was sent
                                        -- 'id', the ID for the request to send that message, provided by the email service provider
            Returns:
                dict - With one field, 'status' that gives the status of the request for the specified message.
                The status can have values 'accepted','sent' or 'failed'

                None - When the Mailer can't connect to the underlying email service provider
        """
        # TODO: This method only returns the state of the request. 
        # We can add more info, for example, reason behind message failing etc.
        pass

    @abc.abstractmethod
    def _process_response(self, response, recepient_email_addresses):
        """
            After the response has been obtained from the request to send a message, this method
            returns a list of dicts, each of them containing two fields:
                -- 'email', the email address to which the message was sent
                -- 'id', the ID for the request to send that message, provided by the email service provider
            The list contains one dict for each entry in the 'to','cc' and 'bcc' fields.
            The send_message() method uses to return its result.

            Args:
                response (requests.models.Response) - Response object obtained after making the call to send
                the message to recepients

                recepient_email_addresses (list) - Contains email addresses of all recepients from to,cc and bcc fields.
                This is used for cases when the backend email service provider provides the same ID for request made to
                send the same message to many recepients.

            Returns:
                list - Each element is a dict with fields 'email' and 'id'
        """
        pass

class MailGunMailer(Mailer):
    """
        Mailer implmementation using MailGun
    """

    def __init__(self):
        """
            Initializes mapping of request statuses returned by MailGun to ones returned by our service.
        """
        self.baseurl = config.MAILGUN_BASEURL
        self._event_status_map = {
            'rejected' : 'processing',
            'failed' : 'failed',
            'accepted' : 'accepted',
            'delivered' : 'sent',
            'compained' : 'sent'
            # Other event types haven't been enabled for this MailGun subscription
        }

    def send_message(self, **params):
        resource = "/messages"
        url = self.baseurl + resource

        auth=("api", config.MAILGUN_KEY)
        data={
            "from": params.get('from_email'),
            "to": params.get('to'),
            "subject": params.get('subject'),
            "text": params.get('text')
        }

        # Gather email addresses of recepients from 'to','cc' and 'bcc' fields
        # Each of these will be given a unique ID by MailGun. This ID will be used
        # to get the status of the respective message later
        recepient_email_addresses = []
        
        # Get (name,email_address) tuples
        to_tuples = MailerUtils.get_name_email_tuples(params.get('to'))
        recepient_email_addresses.extend(single_to_tuple[1] for single_to_tuple in to_tuples)
        if 'cc' in params:
            data['cc'] = params.get('cc')
            cc_tuples = MailerUtils.get_name_email_tuples(params.get('cc'))
            recepient_email_addresses.extend(single_cc_tuple[1] for single_cc_tuple in cc_tuples)

        if 'bcc' in params:
            data['bcc'] = params.get('bcc')
            bcc_tuples = MailerUtils.get_name_email_tuples(params.get('bcc'))
            recepient_email_addresses.extend(single_bcc_tuple[1] for single_bcc_tuple in bcc_tuples)

        # Make & process request
        response = requests.post(url, auth=auth, data=data)
        if(response.status_code == 200):
            messages_info = self._process_response(response.content, recepient_email_addresses)
            return messages_info
        else:
            raise MailNotSentException(response.content, response.status_code)

    def get_message_status(self, message_info):
        resource = "/events"
        url = self.baseurl + resource

        # Get the string for current time in format as specified by RFC 2822
        time2822 = self._get_rfc_2822_time()
        
        try:
            info_response = requests.get(
                url,
                auth=("api", config.MAILGUN_KEY),
                params={
                    "begin"       : time2822,
                    "limit"       :  1,
                    "recipient" : message_info.get('email_address'),
                    "message-id" : message_info.get('id')
                },
                timeout=2 # This is super generous, but keeping this since this is just a prototype application.
                          # For a more serious application, we probably wouldn't rely on querying the dependency each time.
            )

            response_dict = json.loads(info_response.content)
            event = response_dict.get('items',[{}])[0].get('event')
            status = {'status' : self._event_status_map.get(event)}
            return status

        except ConnectTimeout:
            return None

    def _process_response(self, response_content, recepient_email_addresses):
        messages_info = []

        response_json = json.loads(response_content)
        for single_email_address in recepient_email_addresses:
            single_message_info = {}
            single_message_info['email_address'] = single_email_address
            single_message_info['id'] = response_json['id'][1:-1] #ID is enclosed between '<' and '>'
            messages_info.append(single_message_info)

        return messages_info

    def _get_rfc_2822_time(self):
        """
            Returns the string for current time in format as specified by RFC 2822
        """
        nowdt = datetime.datetime.now()
        nowtuple = nowdt.timetuple()
        nowtimestamp = time.mktime(nowtuple)
        time2822 = utils.formatdate(nowtimestamp)
        return time2822

class MandrilMailer(Mailer):
    """
        Mailer implementation using Mandril
    """
    def __init__(self):
        """
            Initializes mapping of request statuses returned by Mandril to ones returned by our service.
        """
        
        self.baseurl = config.MANDRIL_BASEURL
        
        self._event_status_map = {
            'sent' : 'sent',
            'bounced' : 'failed',
            'rejected' : 'failed'
        }

    def send_message(self, **params):
        resource = "/messages/send.json"
        url = self.baseurl + resource

        # Get (name, email_address) tuples for all email fields
        from_name, from_email_addr = MailerUtils.get_name_email_tuple(params.get('from_email'))
        to_tuples = MailerUtils.get_name_email_tuples(params.get('to'))

        cc_tuples = bcc_tuples = []
        if 'cc' in params:
            cc_list = params.get('cc')
            cc_tuples = MailerUtils.get_name_email_tuples(cc_list)
            
        if 'bcc' in params:
            bcc_list = params.get('bcc')
            bcc_tuples = MailerUtils.get_name_email_tuples(bcc_list)

        #Construct body
        recepients = []
        recepients.extend(self._get_recepients_list(to_tuples,'to'))
        recepients.extend(self._get_recepients_list(cc_tuples,'cc'))
        recepients.extend(self._get_recepients_list(bcc_tuples,'bcc'))

        message = {
            "text": params.get('text'),
            "subject": params.get('subject'),
            "from_email": from_email_addr,
            "from_name": from_name,
            "to": recepients
        }

        data = {
            "key": config.MANDRIL_KEY,
            "message": message
        }

        response = requests.post(url, json.dumps(data))
        if(response.status_code == 200):
            messages_info = self._process_response(response.content)
            return messages_info
        else:
            raise MailNotSentException(response.content, response.status_code)

    def _get_recepients_list(self,email_tuples,header_type):
        """
            Mandril requires all recepients to be specified in the same 'to' field, with appropriate
            header types specified i.e. if the recepient should be in to, cc or bcc. 
            This method constructs the list in that format.

            Args:
                email_tuple (list) - List of tuples. Each tuple is of format (name,email_address)
                header_type (str) - If these recepients should go in 'to', 'cc' or 'bcc'

            Returns:
                list - List of dicts. Each dict has the fields 'email', 'name' and 'type' as needed by Mandril.
        """
        recepients_list = []

        if email_tuples is None:
            return recepients_list

        for single_email_tuple in email_tuples:
            name, email_addr = single_email_tuple
            
            recepient = {
                "email":email_addr,
                "name":name,
                "type":header_type
            }
            recepients_list.append(recepient)

        return recepients_list

    def get_message_status(self, message_info):
        resource = "/messages/info.json"
        url = self.baseurl + resource
        
        try:
            info_response = requests.post(
                url,
                json.dumps({
                    "key": config.MANDRIL_KEY,
                    "id" : message_info.get('id')
                    }
                ),
                timeout=2 # Generous, as mentioned above
            )
            
            response_dict = json.loads(info_response.content)
            event = response_dict.get('state')
            status = {'status':self._event_status_map.get(event,'accepted')} #Default is accepted because if the mail isn't delivered, response won't have the state field (null)
            return status

        except ConnectTimeout:
            return None

    def _process_response(self, response_content, recepient_email_addresses = None):
        messages_info = []
        response_json = json.loads(response_content)
        for single_message_info_response in response_json:
            single_message_info = {}
            single_message_info['email_address'] = single_message_info_response['email']
            single_message_info['id'] = single_message_info_response['_id']
            messages_info.append(single_message_info)

        return messages_info 

class MailerUtils:
    @staticmethod
    def get_name_email_tuples(emails_list):
        """
            Takes a list of emails in form as specified by RFC-822 and returns a list that contains
            one (name,email_address) tuple corresponding to each item in the input list.

            Args:
                emails_list (list) - list of emails where each email one is as specified in RFC-822. Ex: 'First Last <first@provider.tld>''

            Returns:
                list - list of tuples where each tuple is of form (name,email_address). Ex: (First Last, first@provider.tld)
        """
        name_email_tuples = []

        if emails_list is None:
            return name_email_tuples

        for email in emails_list:
            name_email_tuple = MailerUtils.get_name_email_tuple(email)
            name_email_tuples.append(name_email_tuple)

        return name_email_tuples

    @staticmethod
    def get_name_email_tuple(name_email_string):
        """
            Takes an email string in form as specified by RFC-822 and returns (name,email_address)
            tuple corresponding to it

            Args:
                name_email_string (string) - String representing an email as specified in RFC-822. Ex: 'First Last <first@provider.tld>''

            Returns:
                tuple - Tuple of form (name,email_address). Ex: (First Last, first@provider.tld). 
                        If the name is absent from the input string, then the first element of the tuple returns None

                None - If the input string is invalid
        """
        if(name_email_string is None):
            return None 
        
        # RegExp credit: http://pymotw.com/2/re/
        pattern = re.compile(
        '''

        # A name is made up of letters, and may include "." for title
        # abbreviations and middle initials.
        ((?P<name>
           ([\w.,]+\s+)*[\w.,]+)
           \s*
           # Email addresses are wrapped in angle brackets: < >
           # but we only want one if we found a name, so keep
           # the start bracket in this group.
           <
        )? # the entire name is optional

        # The address itself: username@domain.tld
        (?P<email>
          [\w\d.+-]+       # username
          @
          ([\w\d.]+\.)+    # domain name prefix
          (com|org|edu)    # TODO: Add more TLDs
        )

        >? # optional closing angle bracket
        ''',
        re.UNICODE | re.VERBOSE)

        match = pattern.search(name_email_string)
        if match:
            groupdict = match.groupdict()
            return groupdict['name'],groupdict['email']
        else:
            return None

    @staticmethod
    def is_email_valid(name_email_string):
        """
            Takes an email string that is supposed to be in the form specified by RFC-822 and 
            returns true or false depending if the string is in valid format or not, respectively
            tuple corresponding to it

            Args:
                name_email_string (string) - String representing an email as specified in RFC-822. Ex: 'First Last <first@provider.tld>''

            Returns:
                bool - Returns result of check of the input string against expected format.
        """
        if name_email_string is None:
            return False
        
        validation_result = MailerUtils.get_name_email_tuple(name_email_string)
        if(validation_result is None or validation_result[1] == None):
            return False

        return True

def get_available_mailers():
    """
        Returns all available implementations of Mailer
        
        Returns:
            list - The list contains all Mailer implementations
    """
    return [MailGunMailer(),MandrilMailer()]

def send_message(**params):
    """
        Tries to send the message with specified parameters & number of retries
        
        Args:
            to (list) - List of emails to send the message to
            from_email (str) - Email to send the message on behalf of
            subject (str) - Subject of the message
            text (str) - Main text that should go in the body of the message
            cc (list) - Optional; list of emails to send the message to, with the 'cc' header
            bcc (list) - Optional; list of emails to send the message to, with the 'bcc' header
            retries (int) - Optional; number of times each Mailer implementation should try to send the message
    
            All email fields are as specified in RFC-822
    """
    retries = params.get('retries', 1) #By default retry 1 time
    
    # TODO: Random shuffling is a crude load-balancing method. Ideally we may want to consider
    # the number of requests to send message made to each Mailer and route new requests accordingly.
    mailers = get_available_mailers()
    shuffle(mailers)

    #TODO: Check if rq has any inbuilt retry mechanism that can be leveraged
    while retries >= 0:
        for mailer in mailers:
            try:
                messages_info = mailer.send_message(**params)
                
                job = get_current_job()
                job.meta['handled_by'] = mailer.__class__.__name__
                job.meta['messages_info'] = messages_info
                job.save()

                # TODO: Use a better way to store status info & metadata for it
                return

            except MailNotSentException as e:
                # TODO: Use logging here to log details of why this mail wasn't sent using
                # e.message & e.status_code. Also, add more details to MailNotSentException
                # if required
                pass
            
            except ConnectTimeout as e:
                # TODO: log
                pass
            
            # Catch other Exceptions that can be thrown here
            
            except Exception as e:
                # If the send_message method fails for any reason whatsoever, we want to use the
                # next Mailer.
                # TODO: Log. These logs will be very important as they'll let us know about failures
                # we're not anticipating
                pass

        retries = retries - 1