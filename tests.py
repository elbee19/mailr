from mailers import MailGunMailer, MandrilMailer, MailerUtils
from mailrexceptions import InvalidInputException, MailNotSentException
from mailr import validate_send_message_input
from mock import patch, Mock
from requests.exceptions import ConnectTimeout
import json
import mailr
import time
import unittest
import mailers

################################################################
# TODO:
# Some of these tests check for specific strings that
# are hardcoded here. This should probably be changed.
# We could define a separate file with just string resources
# & have the tests, as well as application code that returns
# these strings both pull strings from that file
################################################################

# Test functions in mailr.py
class MailrTests(unittest.TestCase):
    
    def setUp(self):
        self.app = mailr.app.test_client()
        self.json_content_type_header = {'content-type':'application/json'} 
    
    ##########################
    # Validation method tests
    ##########################
    def test_validate_send_message_input(self):
        # Raise exception when email is not in a list (for to, cc & bcc)
        self.assertRaises(InvalidInputException,validate_send_message_input,
            {
                 "from" : "Testing API <amitruparel91@gmail.com>",
                 "to" : "bad input",
                 "subject" : "Testing API",
                 "text" : "text!",
                 "cc" : ["Nishant Shah <nish@gmail.com>"]
            })
        
        self.assertRaises(InvalidInputException,validate_send_message_input,
            {
                 "from" : "Testing API <amitruparel91@gmail.com>",
                 "to" : "bad input",
                 "subject" : "Testing API",
                 "text" : "text!",
                 "cc" : "Nishant Shah <nish@gmail.com>"
            })
        
        self.assertRaises(InvalidInputException,validate_send_message_input,
            {
                 "from" : "Testing API <amitruparel91@gmail.com>",
                 "to" : "bad input",
                 "subject" : "Testing API",
                 "text" : "text!",
                 "bcc" : "Nishant Shah <nish@gmail.com>"
            })
        
        # Raise exception when email is invalid
        self.assertRaises(InvalidInputException,validate_send_message_input,
            {
                 "from" : "Testing API <amitrupa@rel91@gmail.com>",
                 "to" : "bad input",
                 "subject" : "Testing API",
                 "text" : "text!",
                 "cc" : ["Nishant Shah <nish@gmail.com>"]
            })
        
        # Raise exception when extra property is supplied
        self.assertRaises(InvalidInputException,validate_send_message_input,
            {
                 "from" : "Testing API <amitruparel91@gmail.com>",
                 "to" : "bad input",
                 "subject" : "Testing API",
                 "text" : "text!",
                 "cc" : ["Nishant Shah <nish@gmail.com>"],
                 "extra" : 2
            })
        
        # Raise exception when required field is missing
        self.assertRaises(InvalidInputException,validate_send_message_input,
            {
                 "to" : "bad input",
                 "subject" : "Testing API",
                 "text" : "text!",
                 "cc" : ["Nishant Shah <nish@gmail.com>"]
            })

    def test_validate_info_input(self):
        
        # Raise exception when email is in invalid format
        self.assertRaises(InvalidInputException,validate_send_message_input,
            {
                 "id" : "45ccde84-78b2-4e91-b460-609d0c678ad5",
                 "email" : "deep@ak201@gmail.com"
            })
        
        # Raise exception when required field is missing
        self.assertRaises(InvalidInputException,validate_send_message_input,
            {
                 "id" : "45ccde84-78b2-4e91-b460-609d0c678ad5"
            })
        
        # Raise exception when extra field is supplied
        self.assertRaises(InvalidInputException,validate_send_message_input,
            {
                 "id" : "45ccde84-78b2-4e91-b460-609d0c678ad5",
                 "email" : "deep@ak201@gmail.com",
                 "extra" : "extra"
            })
    
    ##########################
    # /messages resource tests
    ##########################
    def test_send_message_with_bad_email(self):
        data = {
             "from" : "Testing API <test@gmail.com>",
             "to" : ["tes<t@t>est.com"],
             "subject" : "Testing API",
             "text" : "test"
        }
        
        rv = self.app.post('/messages', data = json.dumps(data), headers = self.json_content_type_header)
        
        assert rv.status_code == 400
        assert 'invalid_emails' in rv.data
    
    def test_send_message_with_incorrect_input_schema(self):
        data = {
             "incorrect_input" : "incorrect_input"
        }
        
        rv = self.app.post('/messages', data = json.dumps(data), headers = self.json_content_type_header)
        
        assert rv.status_code == 400
        assert 'Additional properties are not allowed' in rv.data
        
    def test_send_message_without_json_type(self):
        data = {
             "from" : "Testing API <test@gmail.com>",
             "to" : ["test@test.com"],
             "subject" : "Testing API",
             "text" : "test"
        }
        
        rv = self.app.post('/messages', data = json.dumps(data))
        
        assert rv.status_code == 400
        assert 'Input should be specified in valid JSON format only' in rv.data
    
    """ 
    Commenting this one out as this one really sends messages through the email service providers
    def test_send_message_and_status_with_correct_inputs(self):
        
        # Test /message first
        data = {
             "from" : "Testing API <test@gmail.com>",
             "to" : ["test@test.com"],
             "subject" : "Testing API",
             "text" : "test"
        }
        
        rv = self.app.post('/messages', data = json.dumps(data), headers = self.json_content_type_header)
        
        assert rv.status_code == 202
        assert 'Your request has been accepted' in rv.data
        
        # Now test /status
        resp_dict = json.loads(rv.data)
        
        data = {
            "email" : "test@test.com",
            "id" : resp_dict['id']
        }

        time.sleep(3) #TODO: Too generous. But this fails sometimes with 1 sec sleep. Think about this.
        rv = self.app.post('/status', data = json.dumps(data), headers = self.json_content_type_header)
        
        assert rv.status_code == 200
        assert 'status' in rv.data

    """

    ##########################
    # /status resource tests
    ##########################
    def test_get_status_with_inexistent_id(self):
        data = {
             "id" : "RandomIdThatDoesntExist",
             "email" : "Randomemail@gmail.com"
        }
        rv = self.app.post('/status', data = json.dumps(data), headers = self.json_content_type_header)
        assert rv.status_code == 404
        assert 'Cannot find result for supplied ID and email' in rv.data
    
    def test_get_status_with_incorrect_input_schema(self):
        data = {
             "somekey" :"somevalue"
        }
        rv = self.app.post('/status', data = json.dumps(data), headers = self.json_content_type_header)
        assert rv.status_code == 400
        assert 'Additional properties are not allowed' in rv.data
        
    def test_get_status_without_json_type(self):
        # Response should be 404 with a random id
        data = {
             "somekey" :"somevalue"
        }
        rv = self.app.post('/status', data = json.dumps(data))
        assert rv.status_code == 400
        assert 'Input should be specified in valid JSON format only' in rv.data
    
    ##########################
    # MailGunMailer tests
    ##########################
    @patch('mailers.requests.post', autospec=True)
    def test_mailgun_send_message_successful(self, post):
        
        data = {
             "from_email" : "Testing API <test@gmail.com>",
             "to" : ["test@test.com"],
             "subject" : "Testing API",
             "text" : "test"
        }
        
        post.return_value.status_code = 200
        post.return_value.content = '{ "id" : "<someid>" }'
        
        mailgun_mailer = MailGunMailer()
        messages_info = mailgun_mailer.send_message(**data)
        
        assert len(messages_info) == 1
        assert messages_info[0]['email_address'] == 'test@test.com'
        assert messages_info[0]['id'] == 'someid'
    
    @patch('mailers.requests.post', autospec=True)
    def test_mailgun_send_message_failure(self, post):
        
        data = {
             "from_email" : "Testing API <test@gmail.com>",
             "to" : ["test@test.com"],
             "subject" : "Testing API",
             "text" : "test"
        }
        
        post.return_value.status_code = 400
        
        mailgun_mailer = MailGunMailer()
        self.assertRaises(MailNotSentException,mailgun_mailer.send_message, **data)
    
    @patch('mailers.requests.get', autospec=True)
    def test_mailgun_get_status_successful(self, get):
        
        data = {
         "id" : "45ccde84-78b2-4e91-b460-609d0c678ad5",
         "email" : "deepak201@gmail.com"
        }
        
        get.return_value.status_code = 200
        get.return_value.content = '{ "event" : "delivered" }'
        
        mailgun_mailer = MailGunMailer()
        status_info = mailgun_mailer.get_message_status(data)
        
        assert status_info['status'] == 'sent'
        
    @patch('mailers.requests.get', autospec=True)
    def test_mailgun_get_status_failure(self, get):
        
        data = {
         "id" : "45ccde84-78b2-4e91-b460-609d0c678ad5",
         "email" : "deepak201@gmail.com"
        }
        
        get.side_effect = ConnectTimeout
        
        mailgun_mailer = MailGunMailer()
        status_info = mailgun_mailer.get_message_status(data)
        
        assert status_info == None
    
    ##########################
    # MandriMailer tests
    ##########################
    @patch('mailers.requests.post', autospec=True)
    def test_mandril_send_message_successful(self, post):
        
        data = {
             "from_email" : "Testing API <test@gmail.com>",
             "to" : ["test@test.com"],
             "subject" : "Testing API",
             "text" : "test"
        }
        
        post.return_value.status_code = 200
        post.return_value.content = '[{"email" : "test@test.com", "_id" : "someid"}]'
        
        mandril_mailer = MandrilMailer()
        messages_info = mandril_mailer.send_message(**data)
        
        assert len(messages_info) == 1
        assert messages_info[0]['email_address'] == 'test@test.com'
        assert messages_info[0]['id'] == 'someid'
        
    @patch('mailers.requests.post', autospec=True)
    def test_mandril_end_message_failure(self, post):
        
        data = {
             "from_email" : "Testing API <test@gmail.com>",
             "to" : ["test@test.com"],
             "subject" : "Testing API",
             "text" : "test"
        }
        
        post.return_value.status_code = 400
        
        mandril_mailer = MandrilMailer()
        self.assertRaises(MailNotSentException,mandril_mailer.send_message, **data)
    
    @patch('mailers.requests.post', autospec=True)
    def test_mandril_get_status_successful(self, post):
        
        data = {
         "id" : "45ccde84-78b2-4e91-b460-609d0c678ad5",
         "email" : "deepak201@gmail.com"
        }
        
        post.return_value.status_code = 200
        post.return_value.content = '{ "state" : "sent" }'
        
        mandril_mailer = MandrilMailer()
        status_info = mandril_mailer.get_message_status(data)
        
        assert status_info['status'] == 'sent'
    
    @patch('mailers.requests.post', autospec=True)
    def test_mandril_get_status_failure(self, post):
        
        data = {
         "id" : "45ccde84-78b2-4e91-b460-609d0c678ad5",
         "email" : "deepak201@gmail.com"
        }
        
        post.side_effect = ConnectTimeout
        
        mandril_mailer = MandrilMailer()
        status_info = mandril_mailer.get_message_status(data)
        
        assert status_info == None

    ##########################
    # MailerUtils tests
    ##########################
    def test_is_email_valid(self):
        assert MailerUtils.is_email_valid("Amit Ruparel <amit@ruparel.com>") == True
        assert MailerUtils.is_email_valid("ami@t.com") == True
        assert MailerUtils.is_email_valid("blah") == False
        assert MailerUtils.is_email_valid("") == False
        assert MailerUtils.is_email_valid(None) == False
        # TODO:
        ## assert MailerUtils.is_email_valid("Amit ami#t@rupare.com") == False -- This case needs to be fixed
    
    def test_get_name_email_tuples(self):
        result = MailerUtils.get_name_email_tuples(['amitruparel@gmail.com','Amit Ruparel <aa@gmail.com>'])
        assert len(result) == 2
        assert result[0] == (None, 'amitruparel@gmail.com')
        assert result[1] == ('Amit Ruparel', 'aa@gmail.com')
        
        result = MailerUtils.get_name_email_tuples([None,None])
        assert result == [None,None]
        
        result = MailerUtils.get_name_email_tuples(None)
        assert result == []
        
    ##########################
    # mailers.py tests
    ##########################
    
    @patch('mailers.get_available_mailers', autospec=True)
    @patch('mailers.get_current_job', autospec=True)
    @patch('mailers.shuffle', autospec=True)
    def test_send_message_uses_backups_on_failure(self,shuffle,gcj,get_available_mailers):
        #shuffle should do nothing
        # send_message for mocks 1 & 2 throw, for 3 succeeds & 4's is never called
        mock_mailer_1 = Mock() 
        mock_mailer_1.send_message.side_effect = MailNotSentException('b','c')
        
        mock_mailer_2 = Mock()
        mock_mailer_2.send_message.side_effect = Exception
        
        mock_mailer_3 = Mock()
        mock_mailer_3.send_message.return_value = []
        
        mock_mailer_4 = Mock()
        mock_mailer_4.send_message.return_value = []
        
        get_available_mailers.return_value = [mock_mailer_1,mock_mailer_2,mock_mailer_3,mock_mailer_4]
        gcj.meta = {}
        
        mailers.send_message()
    
        assert mock_mailer_1.send_message.call_count == 1
        assert mock_mailer_2.send_message.call_count == 1
        assert mock_mailer_3.send_message.call_count == 1
        assert mock_mailer_4.send_message.call_count == 0
        

if __name__ == "__main__":
    unittest.main()
