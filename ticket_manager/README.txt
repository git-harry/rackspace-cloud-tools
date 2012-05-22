ticket_manager
This tool is designed to provide an alternative method for creating tickets.
It is designed to work with:
lon.manage.rackspacecloud.com (US)
manage.rackspacecloud.com (UK)


#start a ticket session
tkt = tickets(username, password, region)

#get a lists of your tickets
open_tickets = tkt.list_open()
print open_tickets
closed_tickets = tkt.list_closed()
print closed_tickets
all_tickets = tkt.list_all()
print all_tickets

#create a new ticket and submit it
n_tkt = tkt.create('Test ticket - please ignore', 'Comment 1', 'cloud_servers:general_support', servername='myserver1')
n_tkt.submit()

#get a specific ticket by referencing its ticket number to view all information and comments
a_tkt = tkt.get_ticket(ticket_number)
print a_tkt

#update a ticket by adding the comment to the ticket instance and then submit it
a_tkt.add_comment('Comment 2')
a_tkt.submit()

