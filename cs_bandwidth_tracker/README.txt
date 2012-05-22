This tool is designed to allow you to track the statistics for a network interface as reported by /proc/net/dev
It allows you to compare the statistics the server reports with any bandwidth charges you may incur. You define the day you are billed on and then the tool will track your usage for each calendar month with a start date of that day of the month.
It defines a cron job that runs every ten minutes to get the latest data and appends it to a log file.
You can define limits that, if exceeded, can be used to trigger actions. The two actions that are defined are to send an e-mail or to take down the interface.


To install:
./install

To remove:
./uninstall

To start:
/etc/init.d/cs_bandwidth_tracker start

To stop:
/etc/init.d/cs_bandwidth_tracker stop

Config in /etc/cs_bandwidth_tracker.conf
Must set billing_date. This is the first day of the month for a new billing period
Limits are defined using the following format:

limit_receive_xxx = yyyy
limit_transmit_aaa = bbb

The list of available limits is defined in /proc/net/dev
