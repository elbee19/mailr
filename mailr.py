from flask import Flask, request, render_template
from flask import jsonify
from jsonschema import validate, ValidationError
from mailers import MailerUtils, MailGunMailer, MandrilMailer
from mailrexceptions import InvalidInputException
from redis import Redis
from rq import Queue
import json
import mailers
import logging
import redis
import os
import sys
from logging import StreamHandler

# Setup flask
app = Flask(__name__)

# Setup Redis
redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')
conn = redis.from_url(redis_url)
q = Queue(connection=conn)

# Setup mailers
# When checking status of a message, we'll use the mailers directly as these
# calls shouldn't take too much of time. Also, because our worker doesn't poll
# for status in the background automatically.
# Ideally we should have a worker that polls the underlying email service to get the
# status of the messages that were sent using it
mailgun_mailer = MailGunMailer()
mandril_mailer = MandrilMailer()

available_mailers = {
    mailgun_mailer.__class__.__name__ : mailgun_mailer,
    mandril_mailer.__class__.__name__ : mandril_mailer
}

# Read JSON schemas for input
send_input_schema_dict = None
with open ("./static/send_input_schema.json", "r") as schema_file:
    send_input_schema_string=schema_file.read()
    send_input_schema_dict = json.loads(send_input_schema_string)

info_input_schema_dict = None
with open ("./static/info_input_schema.json", "r") as schema_file:
    info_input_schema_string=schema_file.read()
    info_input_schema_dict = json.loads(info_input_schema_string)


# Index page
# TODO: Implement front end for index
@app.route('/', methods=['GET'])
@app.route('/index', methods=['GET'])
def index():
    return render_template('index.html')

# Resource to send messages
@app.route('/messages', methods=['POST'])
def send_message():
    """
        Call to this resource enqueues the task of sending the message using Redis Queue.
        Once the request is accepted, a response with status code 202 & an ID for the request is sent.
        The user can later poll the result of the request using the status resource.
    """
    # Only accept JSON
    if not request.json:
        resp = create_response("Input should be specified in valid JSON format only",400)
        return resp

    # Validate input
    validate_send_message_input(request.json)

    # To use **kwargs, the parameter name 'form' can't be used as it's a python keyword.
    # So, copy the value from request.json['from'] to request.json['from_email']
    # Other option: The 'from' field from the input schema can be changed to something that's not a python keyword
    # I just feel it's more natural from an end user's perspective to remember the name of the from field is 'from'
    # as opposed to something like from_email
    request.json['from_email'] = request.json['from']

    job = q.enqueue_call(func=mailers.send_message, kwargs=request.json, result_ttl=86400)  # Store result for 1 day
    job_id = job.get_id()
    
    # TODO: The ID returned for a request should definitely be something better than the job_id 
    # of the job enqueues for a serious application.
    info = {'id' : job_id}
    resp = create_response("Your request has been accepted", 202, info)
    return resp

@app.route('/status', methods=['POST'])
def get_status():
    """
        Calls should be made to this resource to get the status of a request earlier enqueued.
        The user should supply the ID of a request made previously, with the email address for which
        the status is desired.

        The input is validated against the JSON schema.

        All email fields can bear values with the name as specified in RFC-822, i.e. First Last <first@provider.tld>
    """
    # Only accept JSON
    if not request.json:
        resp = create_response("Input should be specified in valid JSON format only",400)
        return resp
            
    validate_get_status_input(request.json)

    name, email_address = MailerUtils.get_name_email_tuple(request.json.get('email'))

    # Get the job associated with the given ID from the Queue
    job_id = request.json['id']
    job = q.fetch_job(job_id)
    
    if(job is None):
        resp = create_response("Cannot find result for supplied ID and email", 404)
        return resp

    # Get relevant metadata from the job
    mailer_name = job.meta['handled_by'] # Which mailer was used
    messages_info = job.meta['messages_info'] # Info about all recepients and underlying provider specific ID for the request

    # Get info about the relevant message
    single_message_info = next(message_info for message_info in messages_info if message_info.get('email_address') == email_address)
    if(single_message_info is None):
        resp = create_response("Cannot find message sent to {0} during request with ID {1}".format(email_address,job_id),404)
        return resp

    relevant_mailer = available_mailers[mailer_name]
    status_info = relevant_mailer.get_message_status(single_message_info)
    
    if(status_info is None):
        # Must have timed out
        resp = create_response("This request cannot be served right now. Please try again.", 503)
        return resp

    resp = create_response(None, 200, status_info)
    return resp


def create_response(text, status, info = {}):
    """
        Creates response in a format consistent throughout the application
        Args:
            text (str) - Main text of the response. Returned under the 'message' key
            status (str) - Status code to be returned with the response
            info (dict) - Contains key-value pairs of other properties to be returned with the response.

        Returns:
            requests.models.Response - Response to be returned
    """
    if(text is not None):
        info['message'] = text
    resp = jsonify(info)
    resp.status_code = status
    return resp

def validate_send_message_input(input_dict):
    """
        Validates the input supplied for the POST call on the message resource.

        Args:
            input_dict - JSON input in dictionary form

        Throws:
            InvalidInputException when input is malformed or doesn't match schema
    """

    ## Validate against JSON schema
    try:
        validate(input_dict, send_input_schema_dict)
    except ValidationError as e:
        raise InvalidInputException(e.message)

    ## Validate email addresses
    invalid_emails = []
    
    # Validate from
    from_email = input_dict.get('from')
    if(not MailerUtils.is_email_valid(from_email)):
        invalid_emails.append(from_email)

    # Validate to
    for to_email in input_dict.get('to'):
        if(not MailerUtils.is_email_valid(to_email)):
            invalid_emails.append(to_email)

    # Validate cc
    for to_email in input_dict.get('cc', []):
        if(not MailerUtils.is_email_valid(to_email)):
            invalid_emails.append(to_email)

    # Validate bcc
    for to_email in input_dict.get('bcc',[]):
        if(not MailerUtils.is_email_valid(to_email)):
            invalid_emails.append(to_email)
    
    if(len(invalid_emails)!=0):
        payload = {"invalid_emails":invalid_emails}
        raise InvalidInputException(message = "Input contains invalid email(s)", payload = payload)

def validate_get_status_input(input_dict):
    """
        Validates the input supplied for the POST call on the info resource.

        Args:
            input_dict (dict) - JSON input in dictionary form

        Throws:
            InvalidInputException when input is malformed or doesn't match schema for this call.
    """

    # Validate against JSON schema
    try:
        validate(input_dict, info_input_schema_dict)
    except ValidationError as e:
        raise InvalidInputException(e.message)

    # Validate email address
    email = input_dict.get('email')
    if(not MailerUtils.is_email_valid(email)):
        raise InvalidInputException(message = "Input contains invalid email: "+email)

@app.errorhandler(InvalidInputException)
def handle_invalid_input(error):
    """
        Method to handle InvalidInputException thrown in the application

        Args:
            error (InvalidInputException) - The exception thrown

        Returns:
            requests.models.Response - The response to be returned when this exception is thrown
    """
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

if __name__ == '__main__':
    app.debug = True # Only for development, not prod
    app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.logger.setLevel(logging.DEBUG)
    app.run()
