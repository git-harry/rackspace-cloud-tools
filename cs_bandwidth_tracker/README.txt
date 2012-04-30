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
