#!/bin/bash
# @package ni
# @file install_nilib_wsgi.sh
# @brief Installation script for Apache 2 mod_wsgi usage of nilib Python server
# @version $Revision: 1.00 $ $Author: elwynd $
# @version Copyright (C) 2012 Trinity College Dublin and Folly Consulting Ltd
#       This is an adjunct to the NI URI library developed as
#       part of the SAIL project. (http://sail-project.eu)
# 
#       Specification(s) - note, versions may change
#           - http://tools.ietf.org/html/draft-farrell-decade-ni-10
#           - http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-03
#           - http://tools.ietf.org/html/draft-kutscher-icnrg-netinf-proto-00
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    
#        - http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# 
# ===============================================================================#
# 
# 
# @code
# Revision History
# ================
# Version   Date       Author         Notes
# 1.1	  06/12/2012 Elwyn Davies   Added rsyslog configuration.
# 1.0	  25/11/2012 Elwyn Davies   Created.
# @endcode

# Defaults for configuration
APACHE_USERNAME=www-data
APACHE_GROUPNAME=www-data
NILIB_PATH=/var/netinf
SITES_PATH=/etc/apache2/sites-available
VIRTHOST=netinf.vhost
SERVER=netinf.example.com
EMAIL=webmaster@${SERVER}
NILIB_SRC=/home/nilib/code
NILIB_PYTHON_CONF=/var/niserver
NETINF_SYSLOG_FACILITY=local0
SYSLOG_CONFIG_DIR=/etc/rsyslog.d
NETINF_SYSLOG=${NILIB_PATH}/log/log_mod_wsgi

variables() {
cat <<EOF
Apache user name           $APACHE_USERNAME
Apache group name          $APACHE_GROUPNAME
Root of nilib data tree    $NILIB_PATH
Virtual host files store   $SITES_PATH
File name for virtual host $VIRTHOST
Virtual host server name   $SERVER
Webmaster email address    $EMAIL
Nilib source top directory $NILIB_SRC
Python installed config in $NILIB_PYTHON_CONF
Syslog facility name       $NETINF_SYSLOG_FACILITY
Syslog config directory    $SYSLOG_CONFIG_DIR
Output file for NetInf log $NETINF_SYSLOG

EOF
}

usage() {
cat << EOF
usage: $0 options

This script installs the Apache virtual host file, a minimal configuration
file for the rsyslogd system logger for handling log messages from the 
NetInf mod_wsgi module, and data area that allows the Python nilib code to 
be used via mod_wsgi to manage a NetInf NDO cache.

*** The script must be run as root!

OPTIONS:
    -h              Show this message
    -u <username>   The name of the user that Apache uses when running
    -g <groupname>  The name of the group that Apache uses when running
    -r <path>       The path to be used as the root of the nilib data tree
    -v <path>       The directory where Apache virtual host files are stored 
    -n <virthost>   The name to be used for the Apache virtual host
    -a <auth>       The Apache server name for the virtual host
    -e <email>      The email address for the webmaster of the virtual host
    -s <path>       Top level directory where makefile for nilib is located
    -c <path>       The path where the installed Python nilib has its config data
    -f <facility>   Name of syslog facility to be used ('local0' ... 'local9')
    -d <path>       Directory where rsyslog configuration files are stored
    -l <filepath>   File name for syslog output file (absolute path)

Assumes installation is using rsyslog - if not the syslog will have to be
configured manually.

Defaults:
EOF

variables
}

email_set=0
while getopts "hu:g:r:v:n:a:e:s:c:f:d:l:" OPTION; do
    case $OPTION in
        h)
            usage
            exit 1
            ;;
        u)
            APACHE_USERNAME=$OPTARG
            ;;
        g)
            APACHE_GROUPNAME=$OPTARG
            ;;
        r)
            NILIB_PATH=$OPTARG
            ;;
        v)
            SITES_PATH=$OPTARG
            ;;
        n)
            VIRTHOST=$OPTARG
            ;;
        a)
            SERVER=$OPTARG
	    if [[ $email_set -eq 0 ]]; then
              EMAIL=webmaster@${SERVER}
	    fi
            ;;
        e)
            EMAIL=$OPTARG
	    email_set=1
            ;;
        s)
            NILIB_SRC=$OPTARG
            ;;
        c)
            NILIB_PYTHON_CONF=$OPTARG
            ;;
        f)
            NETINF_SYSLOG_FACILITY=$OPTARG
            ;;
        d)
            SYSLOG_CONFIG_DIR=$OPTARG
            ;;
        l)
            NETINF_SYSLOG=$OPTARG
            ;;
        ?)
            usage
            exit 1
    esac
done

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 1>&2
   exit 1
fi

echo "Checking directories exist..."
if [[ ! -d $SITES_PATH ]]; then
  echo "Apache virtual host files directory $SITES_PATH does not exist"
  exit 1
fi
if [[ ! -d $NILIB_SRC ]]; then
  echo "Nilib source directory $NILIB_SRC does not exist"
  exit 1
fi
if [[ ! -d $SYSLOG_CONFIG_DIR ]]; then
  echo "rsyslog configuration directory $SYSLOG_CONFIG_DIR does not exist"
  exit 1
fi


echo "Checking for possible overwrites..."
if [[ -f ${SITES_PATH}/${VIRTHOST} ]]; then
  echo "Virtual host file $VIRTHOST exists."
  echo -n "Are you sure you want to overwrite it? [y/n] "
  read answer
  if [[ x$answer != "xy" ]]; then
    echo "Abandoning installation"
    exit 1
  fi
fi

cache_archived=0
if [[ -d ${NILIB_PATH} ]]; then
  echo "Nilib data tree directory $NILIB_PATH exists." 
  echo -n "Do you want to backup the NDO cache (if any)? [y/n] "
  read answer
  if [[ x$answer == "xy" ]]; then
    if [[ -d ${NILIB_PATH}/cache ]]; then
      cache_archive_name=/tmp/ndo_cache_`date +%s`
      tar czf $cache_archive_name -C ${NILIB_PATH} cache
      if [[ $? -ne 0 ]]; then
	echo "Cache archiving failed.. aborting installation"
	exit 1
      fi
      echo "NDO cache archived in $cache_archive_name"
      cache_archived=1
    fi
  fi
  echo -n "Are you sure you want to overwrite data tree? [y/n] "
  read answer
  if [[ x$answer != "xy" ]]; then
    echo "Abandoning installation"
    exit 1
  fi
fi

echo "Ready to install nilib mod_wsgi virtual host setup"
echo "Using the following configuration..."
variables

echo -n "OK to proceed with installation? [y/n] "
read answer
if [[ x$answer != "xy" ]]; then
  echo "Abandoning installation."
  exit 1
fi

echo "Starting installation"

echo "Creating Python documentation..."
cd $NILIB_SRC
make pydoxy
if [[ $? -ne 0 ]]; then
  echo "Documentation creation failed.. abandoning installation."
  exit 1
fi

echo "Installing Python module..."
cd python
sudo python setup.py install
if [[ $? -ne 0 ]]; then
  echo "Python module installation failed.. abandoning installation."
  exit 1
fi

echo "Checking this has created expected configuration directory..."
if [[ ! -d ${NILIB_PYTHON_CONF}/wsgi ]]; then
  echo "Python installation did not create ${NILIB_PYTHON_CONF}/wsgi... Abandoning installation."
  exit 1
fi

echo "Making nilib data directory and contents..."
if [[ -d $NILIB_PATH ]]; then
  echo "Removing old version..."
  rm -rf $NILIB_PATH
  if [[ $? -ne 0 ]]; then
    echo "Unable to remove old nilib data directory.. abandoning installation."
    exit 1
  fi
fi
mkdir -p $NILIB_PATH

echo "Setting ownership of ${NILIB_PATH}..."
chown -R ${APACHE_USERNAME}.${APACHE_GROUPNAME} $NILIB_PATH

echo "Copying data to ${NILIB_PATH}..."
sudo -u $APACHE_USERNAME cp -r ${NILIB_PYTHON_CONF}/wsgi/* $NILIB_PATH
sudo -u $APACHE_USERNAME cp -r ${NILIB_SRC}/python/doc/html/* ${NILIB_PATH}/doc
if [[ $cache_archived -eq 1 ]]; then
  echo "Restoring cache archive from ${cache_archive_name}..."
  sudo -u $APACHE_USERNAME tar xzf $cache_archive_name -C $NILIB_PATH
  if [[ $? -ne 0 ]]; then
    echo "Restore of cache failed"
  fi
fi
echo "Creating Apache virtual host file..."
cat <<EOF >${SITES_PATH}/${VIRTHOST}
<VirtualHost *:80>
	ServerName $SERVER

	ServerAdmin $EMAIL

	DocumentRoot ${NILIB_PATH}/www
	<Directory ${NILIB_PATH}/www/>
		Options Indexes FollowSymLinks MultiViews
		AllowOverride None
		Order allow,deny
		allow from all
	</Directory>

	ScriptAlias /cgi-bin/ /usr/lib/cgi-bin/
	<Directory "/usr/lib/cgi-bin">
		AllowOverride None
		Options +ExecCGI -MultiViews +SymLinksIfOwnerMatch
		Order allow,deny
		Allow from all
	</Directory>

	# WSGI setup
	WSGIDaemonProcess $SERVER  processes=2 threads=15 display-name=%{GROUP}
	WSGIProcessGroup $SERVER

	WSGIScriptAlias /testapp ${NILIB_PATH}/wsgi-apps/test.wsgi
	WSGIScriptAlias /envapp ${NILIB_PATH}/wsgi-apps/showenv.wsgi
	WSGIScriptAlias /netinfproto ${NILIB_PATH}/wsgi-apps/netinf.wsgi
	WSGIScriptAlias /.well-known/ni ${NILIB_PATH}/wsgi-apps/netinf.wsgi
	WSGIScriptAlias /ni_cache ${NILIB_PATH}/wsgi-apps/netinf.wsgi
	WSGIScriptAlias /ni_meta ${NILIB_PATH}/wsgi-apps/netinf.wsgi
	WSGIScriptAlias /ni_qrcode ${NILIB_PATH}/wsgi-apps/netinf.wsgi

	SetEnv NETINF_STORAGE_ROOT ${NILIB_PATH}/cache
	SetEnv NETINF_GETPUTFORM ${NILIB_PATH}/www/getputform.html
	SetEnv NETINF_NRSFORM ${NILIB_PATH}/www/nrsconfig.html
	SetEnv NETINF_FAVICON ${NILIB_PATH}/www/favicon.ico
	SetEnv NETINF_PROVIDE_NRS no
	SetEnv NETINF_SYSLOG_FACILITY $NETINF_SYSLOG_FACILITY
	SetEnv NETINF_LOG_LEVEL NETINF_LOG_INFO

	<Directory ${NILIB_PATH}/wsgi-apps/>
		Order allow,deny
		allow from all
	</Directory>

	ErrorLog \${APACHE_LOG_DIR}/error.log

	# Possible values include: debug, info, notice, warn, error, crit,
	# alert, emerg.
	LogLevel warn

	CustomLog \${APACHE_LOG_DIR}/access.log combined

    # Make the Python Doxygen docs visible
    Alias /doc ${NILIB_PATH}/doc
    <Directory "${NILIB_PATH}/doc/">
        Options Indexes MultiViews FollowSymLinks
        AllowOverride None
        Order deny,allow
        Allow from all
    </Directory>

</VirtualHost>
EOF

echo "Creating rsyslog configuration file ${SYSLOG_CONFIG_DIR}/60-netinf.conf ..."
cat <<EOF >${SYSLOG_CONFIG_DIR}/60-netinf.conf
# Logging setup used for NetInf mod_wsgi application in Apache
# Write all messages to single file as a starting position
${NETINF_SYSLOG_FACILITY}.* ${NETINF_SYSLOG}
EOF

echo "Checking if script to enable virtual host exists..."
if [[ -x /usr/sbin/a2ensite ]]; then
  echo "Using a2ensite to enable virtualhost..."
  /usr/sbin/a2ensite ${VIRTHOST}
  echo "Now either use \"sudo apache2ctl graceful\" or"
  echo "\"sudo service apache2 reload\" to enable new virtual host"
else
  echo "Please enable virtual host and restart Apache (gracefully)."
  echo "The command \"sudo apache2ctl graceful\" should do the restart."
fi
echo "Please use \"sudo service rsyslog restart\" to activate logging for mod_wsgi."
echo "Installation successfully done"
echo ""
echo "Post-installation setup:"
echo "Please access http://${SERVER}/checkcache once the installation"
echo "is complete.  This will ensure the cache directory structure"
echo "is initialized"

exit 0

