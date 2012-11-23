#!/usr/bin/python
"""
@package nilib
@file test_wsgi.py
@brief Basic tests for wsgishim.py
@version $Revision: 1.00 $ $Author: elwynd $
@version Copyright (C) 2012 Trinity College Dublin and Folly Consulting Ltd
      This is an adjunct to the NI URI library developed as
      part of the SAIL project. (http://sail-project.eu)

      Specification(s) - note, versions may change
          - http://tools.ietf.org/html/draft-farrell-decade-ni-10
          - http://tools.ietf.org/html/draft-hallambaker-decade-ni-params-03
          - http://tools.ietf.org/html/draft-kutscher-icnrg-netinf-proto-00

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
   
       - http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

================================================================================

@details
wsgishim.py tests overview

Simple tests for classes HeaderDict and the WSGI version of HTTPRequestShim.

Logging output is written to stderr.

The test output is written to stdout.

@code
Revision History
================
Version   Date       Author         Notes
1.0       22/11/2012 Elwyn Davies   Created..

@endcode
"""

#==============================================================================#
import sys
from wsgishim import HTTPRequestShim, HeaderDict
from StringIO import StringIO
import os

#==== TEST DATA ====
environ = {
    "ANT_HOME": "/usr/share/ant",
    "CLASSPATH": ".:.:/opt/sun-jdk-1.6.0.15/jre/lib/",
    "COLORTERM": "gnome-terminal",
    "CONFIG_PROTECT": "/usr/share/X11/xkb",
    "CONFIG_PROTECT_MASK": "/etc/sandbox.d /etc/env.d/java/ /etc/php/cli-php5/ext-active/ /etc/php/cgi-php5/ext-active/ /etc/php/apache2-php5/ext-active/ /etc/udev/rules.d /etc/fonts/fonts.conf /etc/gconf /etc/terminfo /etc/ca-certificates.conf /etc/texmf/web2c /etc/texmf/language.dat.d /etc/texmf/language.def.d /etc/texmf/updmap.d /etc/revdep-rebuild",
    "CONTENT_LENGTH": "",
    "CONTENT_TYPE": "text/plain",
    "CVS_RSH": "ssh",
    "DBUS_SESSION_BUS_ADDRESS": "unix:abstract=/tmp/dbus-TF0snuGdfM,guid=57d73fdb0e45a0b570859df90000003e",
    "DESKTOP_SESSION": "gnome",
    "DISPLAY": ":0.0",
    "EDITOR": "/usr/bin/vim",
    "GATEWAY_INTERFACE": "CGI/1.1",
    "GCC_SPECS": "",
    "GDK_USE_XFT": "1",
    "GDMSESSION": "gnome",
    "GDM_LANG": "C",
    "GDM_XSERVER_LOCATION": "local",
    "GNOME_DESKTOP_SESSION_ID": "this-is-deprecated",
    "GNOME_KEYRING_PID": "4485",
    "GNOME_KEYRING_SOCKET": "/tmp/keyring-AmCwC4/socket",
    "GTK_RC_FILES": "/etc/gtk/gtkrc:/home/elwynd/.gtkrc-1.2-gnome2",
    "GUILE_LOAD_PATH": "/usr/share/guile/1.8",
    "HG": "/usr/bin/hg",
    "HOME": "/home/elwynd",
    "HTTP_ACCEPT": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "HTTP_ACCEPT_CHARSET": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
    "HTTP_ACCEPT_ENCODING": "gzip,deflate",
    "HTTP_ACCEPT_LANGUAGE": "en-us,en;q=0.5",
    "HTTP_CONNECTION": "keep-alive",
    "HTTP_HOST": "localhost:8052",
    "HTTP_KEEP_ALIVE": "115",
    "HTTP_USER_AGENT": "Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3",
    "INFOPATH": "/usr/share/info:/usr/share/binutils-data/i686-pc-linux-gnu/2.18/info:/usr/share/gcc-data/i686-pc-linux-gnu/4.1.2/info",
    "JAVAC": "/home/elwynd/.gentoo/java-config-2/current-user-vm/bin/javac",
    "JAVA_HOME": "/opt/sun-jdk-1.6.0.15",
    "JDK_HOME": "/home/elwynd/.gentoo/java-config-2/current-user-vm",
    "LANG": "C",
    "LESS": "-R -M --shift 5",
    "LESSOPEN": "|lesspipe.sh %s",
    "LOGNAME": "elwynd",
    "LS_COLORS": "rs=0:di=01;34:ln=01;36:mh=00:pi=40;33:so=01;35:do=01;35:bd=40;33;01:cd=40;33;01:or=01;05;37;41:mi=01;05;37;41:su=37;41:sg=30;43:ca=30;41:tw=30;42:ow=34;42:st=37;44:ex=01;32:*.tar=01;31:*.tgz=01;31:*.arj=01;31:*.taz=01;31:*.lzh=01;31:*.lzma=01;31:*.tlz=01;31:*.txz=01;31:*.zip=01;31:*.z=01;31:*.Z=01;31:*.dz=01;31:*.gz=01;31:*.lz=01;31:*.xz=01;31:*.bz2=01;31:*.bz=01;31:*.tbz=01;31:*.tbz2=01;31:*.tz=01;31:*.deb=01;31:*.rpm=01;31:*.jar=01;31:*.rar=01;31:*.ace=01;31:*.zoo=01;31:*.cpio=01;31:*.7z=01;31:*.rz=01;31:*.jpg=01;35:*.jpeg=01;35:*.gif=01;35:*.bmp=01;35:*.pbm=01;35:*.pgm=01;35:*.ppm=01;35:*.tga=01;35:*.xbm=01;35:*.xpm=01;35:*.tif=01;35:*.tiff=01;35:*.png=01;35:*.svg=01;35:*.svgz=01;35:*.mng=01;35:*.pcx=01;35:*.mov=01;35:*.mpg=01;35:*.mpeg=01;35:*.m2v=01;35:*.mkv=01;35:*.ogm=01;35:*.mp4=01;35:*.m4v=01;35:*.mp4v=01;35:*.vob=01;35:*.qt=01;35:*.nuv=01;35:*.wmv=01;35:*.asf=01;35:*.rm=01;35:*.rmvb=01;35:*.flc=01;35:*.avi=01;35:*.fli=01;35:*.flv=01;35:*.gl=01;35:*.dl=01;35:*.xcf=01;35:*.xwd=01;35:*.yuv=01;35:*.cgm=01;35:*.emf=01;35:*.axv=01;35:*.anx=01;35:*.ogv=01;35:*.ogx=01;35:*.pdf=00;32:*.ps=00;32:*.txt=00;32:*.patch=00;32:*.diff=00;32:*.log=00;32:*.tex=00;32:*.doc=00;32:*.aac=00;36:*.au=00;36:*.flac=00;36:*.mid=00;36:*.midi=00;36:*.mka=00;36:*.mp3=00;36:*.mpc=00;36:*.ogg=00;36:*.ra=00;36:*.wav=00;36:*.axa=00;36:*.oga=00;36:*.spx=00;36:*.xspf=00;36:",
    "MANPATH": "/home/elwynd/.gentoo/java-config-2/current-user-vm/man:/usr/local/share/man:/usr/share/man:/usr/share/binutils-data/i686-pc-linux-gnu/2.18/man:/usr/share/gcc-data/i686-pc-linux-gnu/4.1.2/man:/etc/java-config/system-vm/man/:/usr/lib/php5/man/:/usr/qt/3/doc/man",
    "OLDPWD": "/home/elwynd/python/mod_wsgi-3.4",
    "OPENGL_PROFILE": "xorg-x11",
    "ORBIT_SOCKETDIR": "/tmp/orbit-elwynd",
    "PAGER": "/usr/bin/less",
    "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/bin:/usr/i686-pc-linux-gnu/gcc-bin/4.1.2:/usr/qt/3/bin:/usr/lib/subversion/bin:/usr/games/bin:/home/elwynd/scripts:/opt/sun-jdk-1.6.0.15/bin:/opt/sun-jre-bin-1.6.0.15/bin:.",
    "PATH_INFO": "/",
    "PKG_CONFIG_PATH": "/usr/qt/3/lib/pkgconfig",
    "PWD": "/home/elwynd/python",
    "PYTHONDOCS": "/usr/share/doc/python-docs-2.6.4/html/library",
    "PYTHONDOCS_2_6": "/usr/share/doc/python-docs-2.6.4/html/library",
    "PYTHONPATH": "/home/elwynd/Python/pypop:/home/elwynd/Python/PyMail/gateway/dtn/python/pymail_gateway:/home/elwynd/Python/pypop:/home/elwynd/Python/PyMail/gateway/dtn/python/pymail_gateway:/home/elwynd/DTN/dtn-2.8.0/netinf-code/python",
    "QMAKESPEC": "linux-g++",
    "QTDIR": "/usr/qt/3",
    "QUERY_STRING": "",
    "REMOTE_ADDR": "127.0.0.1",
    "REMOTE_HOST": "mightyatom.folly.org.uk",
    "REQUEST_METHOD": "GET",
    "SCRIPT_NAME": "",
    "SERVER_NAME": "mightyatom.folly.org.uk",
    "SERVER_PORT": "8052",
    "SERVER_PROTOCOL": "HTTP/1.1",
    "SERVER_SOFTWARE": "WSGIServer/0.1 Python/2.6.4",
    "SESSION_MANAGER": "local/mightyatom:@/tmp/.ICE-unix/4499,unix/mightyatom:/tmp/.ICE-unix/4499",
    "SHELL": "/bin/bash",
    "SHLVL": "1",
    "SSH_AGENT_PID": "4530",
    "SSH_AUTH_SOCK": "/tmp/keyring-AmCwC4/socket.ssh",
    "TERM": "xterm",
    "USER": "elwynd",
    "USERNAME": "elwynd",
    "VBOX_APP_HOME": "/usr/lib/virtualbox",
    "WINDOWID": "45593922",
    "WINDOWPATH": "7",
    "XAUTHORITY": "/tmp/.gdm4R7PJW",
    "XDG_CONFIG_DIRS": "/etc/xdg",
    "XDG_DATA_DIRS": "/usr/local/share:/usr/share:/usr/share/gdm",
    "XDG_MENU_PREFIX": "gnome-",
    "XDG_SESSION_COOKIE": "4c990fef93972d772b6bb3d7000000f7-1345466881.984785-1669971938",
    "XERCESC_NLS_HOME": "/usr/share/xerces-c/msg",
    "_": "/usr/bin/python",
    "wsgi.errors": sys.stderr,
    "wsgi.file_wrapper": None,
    "wsgi.input": None,
    "wsgi.multiprocess": "False",
    "wsgi.multithread": "True",
    "wsgi.run_once": "False",
    "wsgi.url_scheme": "http",
    "wsgi.version": "(1, 0)",
    "NETINF_STORAGE_ROOT": "/tmp/cache",
    "NETINF_GETPUTFORM": "/var/niserver/getputform.html",
    "NETINF_NRSFORM": "/var/niserver/nrsconfig.html",
    "NETINF_FAVICON": "/var/niserver/favicon.ico",
    "NETINF_PROVIDE_NRS": "no"
}

#==============================================================================#
# TESTING CODE
#==============================================================================#
#==== TEST CLASS ====
class TestHandler(HTTPRequestShim):
    """
    @brief Simple test of WSGI handler shim on its own.

    Generates a plain text response consisting of two random strings
    and the content of the file /etc/group in between, testsing
    send_string and send_file and some basic headers.
    """
    def do_GET(self):
        print self.rfile.read()
        s = "***Some body\n"
        rl = len(s)
        self.send_string(s)
        f = open("/etc/group", "rb")
        f.seek(0,os.SEEK_END)
        rl += f.tell()
        f.seek(0, os.SEEK_SET)
        self.send_file(f)
        s = "\n***After the file\n"
        rl += len(s)
        self.send_string(s)
        self.send_string({})
        self.send_header("Content-Length", str(rl))
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        #self.send_error(404, "Don't be stupid")
        self.send_response(200, "OK")
        return
        
#==== TEST FUNCTIONS ====

def test_headers(environ):
    """
    @brief Test for HeaderDict
    """
    headers = HeaderDict(environ)
    try:
        print headers["xxx"]
    except KeyError:
        print "Key xxx correctly not found"
    print headers.get("xxx")
    try:
        print headers["hg"]
    except KeyError:
        print "Key hg correctly not found"
    print headers["Content-Type"]
    print headers["Accept"]
    print headers
    for k in headers:
        print "%s::: %s" % (k, headers[k])
    del headers["Keep-Alive"]
    print headers
    headers["Keep-Alive"] = "265"
    print headers
    try:
        print headers["xxx"]
    except KeyError:
        print "Key xxx correctly not found"
    return

#-------------------------------------------------------------------------------#
def start_response(status, headers):
    """
    @@brief Dummy version of start_response function supplied by WSGI

    Just prints status line and hedaers
    """
    print status
    print headers
    return

#-------------------------------------------------------------------------------#
def test_shim(environ):
    """
    @brief Basic tests for WSGI version of HTTPRequestShim

    Sets up a dummy request body file and incorporates NetInf environment
    variables in environ dictionary.

    Create an instance of the dumy handler class which generates a dummy
    response body.  The results are printed out.
    """
    inputfile = StringIO()
    inputfile.write("Some input")
    inputfile.seek(0)
    environ["wsgi.input"] = inputfile

    h = TestHandler(sys.stderr)
    y = h.handle_request(environ, start_response)
    if y is None:
        print "Empty response"
    else:
        for s in y:
            print s

#==============================================================================#
# EXECUTE TESTS
#==============================================================================#
print "Testing HeaderDict...."
test_headers(environ)

print "\n\nTesting HTTPRequestShim..."
test_shim(environ)

print "\n\nTests finished"

