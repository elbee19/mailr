~~Edit (7th Apr, 10:00 am): I just realized there still may be a couple of issues with the site deployed on Heroku which would render it defunct (the Redis Queue worker doesn't execute jobs). However this app works absolutely fine locally. If you'd like to run it locally, I'd be happy to supply you wih my config variable including the API keys. Please just shoot me an email at amitruparel91 (at) Google'sMailService.com. I'll still try to debug & fix this as soon as I can but it is going to be a little difficult since I'm on call this week. Thanks!


Edit (7th Apr, 11:30 pm): Fixed the issue! :)


**MAILR - The Email Service for the [Uber Coding Challenge](https://github.com/uber/coding-challenge-tools)**
-----------------------------------------------------------

**Problem**:
We need a super reliable Email service. It should 

 - Take the necessary inputs to send emails 
 - Take dependencies on
 - Use another
   underlying email service if the first one fails
 - Abstract the details
   of these services from the end user

**Solution**:
Enter Mailr - our web 2.0 email service. Mailr uses 2 underlying services (MailGun & Mandril) to serve its users' needs. With Mailr you can:

- Send emails
	- You can either use the UI to send emails, or
	- Send a POST request to the /messages resource with a JSON body. The JSON body has to have fields 'to', 'from', 'text' and 'subject' necessarily. Fields 'cc' and 'bcc' are optional.
	- All the recipient fields i.e. 'to', 'cc' and 'bcc' are supposed to be lists.
	- Each of the recepients in the list can be specified in the format as described by RFC 822. Ex: Firstname Lastname <<id@emailprovider.tld>>
	- So a sample request body would look like:

>     {
>        "from":"Amit Ruparel <amit@gmail.com>",
>        "to":[
>           "nishantshah@live.com"
>        ],
>        "subject":"Hello",
>        "text":"Testing some Mailr awesomness!",
>        "cc":[
>           "deepak@hotmail.com"
>        ],
>        "bcc":[
>           "Jay Patel <jay@silverrails.tech>",
>           "sagar@jhobalia.com"
>        ]
>     }

- 
	- A successful request to this resource would return a response with code 202 and message body like the following. It doesn't guarantee delivery of email, but simply queues the request to send the email. 

>     {
>        "id":"0928f70a-9783-4517-8345-db49ce3f63da",
>        "message":"Your request has been accepted"
>     }

- 
	- The 'id' can be used to get the status of the message later.
	- To get the status of a sent message, the id must be supplied with one of the recepients' email address.

- Check email status
	- You can either use the UI to check the status of a previously sent message, or
	- Make a POST request with a JSON body to the /status resource, that would contain the fields 'email' and 'id'. It would look like this:

>     {
>      "id" : "45ccde84-78b2-4e91-b460-609d0c678ad5",
>      "email" : "deepak201@gmail.com"
>     }

- 
	- A successful response to this call would return a JSON body with just one field called 'status' which can have values 'accepted', 'sent' or 'failed'
	- Status of emails are preserved for 24 hours, after which the server would respond with a 404 for an expired 'id'

**Solution focus**:
Backend

**Architecture/Stack Decisions & Notes**:
Stack used for this project: Flask, Bootstrap, Redis Queue. This was my first experience with Python OOP, Flask & a Task Queue.

I considered using Django initially but on some light research, Flask seemed more appropriate for this project where the API was the main focus. Flask provides a very simple & lightweight framework to host APIs.

The requirement of the project is to use multiple underlying email services such that, when one fails, the other can be used. This made it clear that having an async task running in the background to process requests was good idea. Once a user makes a call to send an email, we wouldn't want them to be waiting, so we let them know the request is accepted with a 202 and enqueue the task.

I came across the idea of Task Queues on looking up how to schedule background jobs in Flask. Celery was the other option I had in mind but from light research, Redis Queue with the rq library seemed much simpler to use. Just like Flask, it is lightweight and seemed very appropriate for the task.

I used Bootstrap make the UI look better than what vanilla HTML provides & to leverage some predefined CSS styles. I wrote some custom style classes, which I added to the bootstrap css file & also wrote some jQuery code to call the backend from the HTML forms. 

PS: I'm aware the UI code could have been better structured & written, but I didn't pay much attention to it since I was focussing on the backend.

**Possible Improvements**:
If I had more time, I'd consider taking care of the following things (in no order):

Code/Arch-related:

 - Add tests around Redis Queue.
 - Add realtime tests (Tests that actually send and receive emails)
 - Right now the 'id' returned on making a request to send an email is
   just the job id of job enqueued in RQ. And the meta-data to get the
   status is obtained from the job result - after which the underlying
   email service provider is polled. The user gets a 503 code if the
   call to underlying service provider times out. Ideally, we would want
   to store meta-data about enqueued jobs in a more structured way, and
   obtain the status of all requests that were made from the underlying
   provider through another worker process.
 - In case of failures, we should gather more information about why the
   message failed and convey it to the end user with the right amount of
   abstraction.

Product-related:

 - Give users more options to send emails (like send HTML text, schedule
   emails or attachments)
 - Ability to send mail requests using something like Twilio would be
   really cool
 - Add more email providers
 - Improve UI
 - 

**Public Profiles**:
[Facebook](https://www.facebook.com/ruparel.a)
[LinkedIn](https://www.linkedin.com/profile/view?id=86149536)

[**Resume**](https://www.dropbox.com/s/33ya26eb8ee006q/AmitRuparelPostMSFT.pdf?dl=0)
[**Demo**](https://secret-sierra-6425.herokuapp.com/)
