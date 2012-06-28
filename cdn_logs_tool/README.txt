Rackspace Cloud CDN log tool

The purpose of this tool is to provide a simple method for accessing Rackspace
Cloud Files CDN log files. The files are all stored in a single container and 
this tool allows you to pick out the logs relating to a particular container as
well as filter them by date or select the most recent.

usage: cdn_logs.py [-h] [--nocache] [--num_files NUM_FILES]
                   [--start_date YYYY/MM/DD/HH] [--end_date YYYY/MM/DD/HH]
                   [--analyse] [--snet]
                   username apikey region container

--nocache - by default the tool will cache the logs on your system to reduce
            network traffic and increase the speed of subsequent requests.
--num_files - works back from the most recent log getting the number of files
              specified.
--start_date - gets files newer than this date. Note that to get files newer 
               than a particular day you need to specify the hour as 23.
--end_date - specifies the date of the newest logs to get
--analyse - provides some simple analysis of the log data
--snet - if you are using a cloud system, e.g. cloud server, in the same data
         centre as your cloud files account you can use this option to prevent
         bandwidth charges.
