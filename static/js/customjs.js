function submitsendform()
{
	var from = $('#from').val();
	var to = $('#to').val();
	var cc = $('#cc').val();
	var bcc = $('#bcc').val();
	var subject = $('#subject').val();
	var text = $('#text').val();

	var data = {};
	if(!isBlank(to))
	{
		data['to'] = csvToList(to);
	}
	if(!isBlank(from))
	{
		data['from'] = from;
	}
	if(!isBlank(cc))
	{
		data['cc'] = csvToList(cc);
	}
	if(!isBlank(cc))
	{
		data['bcc'] = csvToList(bcc);
	}
	if(!isBlank(text))
	{
		data['text'] = text;
	}
	if(!isBlank(subject))
	{
		data['subject'] = subject;
	}

	$.ajax({
        data: JSON.stringify(data),
        type: 'POST',
        url: './messages',
        contentType: 'application/json',
        complete: function(response) {
            $('#result').html(response['responseText']);
    }})

	return false;
}

function submitgetstatusform()
{
	var email = $('#email').val();
	var id = $('#id').val();

	var data = {};
	if(!isBlank(email))
	{
		data['email'] = email;
	}
	if(!isBlank(id))
	{
		data['id'] = id;
	}

	$.ajax({
        data: JSON.stringify(data),
        type: 'POST',
        url: './status',
        contentType: 'application/json',
        complete: function(response) {
            $('#result').html(response['responseText']);
    }})

	return false;
}

function csvToList(value) {
	return value.split(',');
}

function isBlank(value) {
  return value == null || $.trim(value) == '';
}