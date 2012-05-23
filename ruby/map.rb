#
# NI Routing Table
#
# This is the NI URI library developed as
# part of the SAIL project. (http://sail-project.eu)
#
# Specification(s) - note, versions may change::
# * http://tools.ietf.org/html/farrell-decade-ni
# * http://tools.ietf.org/html/draft-hallambaker-decade-ni-params
#
# Author:: Dirk Kutscher <kutscher@neclab.eu>
# Copyright:: Copyright (c) 2012 Dirk Kutscher <kutscher@neclab.eu>
#
# License:: http://www.apache.org/licenses/LICENSE-2.0.html
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.



require 'mapdsl'

#mapNi will map the specified resource to an NI name and make this
#available. You have to specify the resource identifier (HTTP URI or
#file URI), the authority (can be empty string), and you can
#optionally specify options (see examples).

#mapNi maps exactly one resource to an NI name.

#map <URI> <auth> <options>
#URI: <file-URI> | <http-URI>

#mapNi "http://www.ietf.org/images/ietflogotrans.gif",  "www.ietf.org"
#map "file:///tmp/file", "example.com", {:hash-algo => "sha-256"}
#map "file:///var/music", "example.com", {:recurse => true}
mapNi localFile("stephen.jpg"), "example.com"
mapNi localFile("README"), "neclab.eu"



#mountNi will install a mapping that is transforming the NI URI to
#another URI (HTTP URI or file URI). The transformation specification
#will be executed in the context of the NI object, i.e., you can use
#NI member functions to access URI elements.


# the .well-known mapping
mountNi '"http://#{@host}/.well-known/ni/#{hashAlgo.to_s}/#{hashAsBase64 + queryPart}"'

# mapping to a local file system, using the content type parameter
mountNi '"file:///var/ni/media/#{contentType}/#{algo}/#{hashAsBase64}"'

# mapping to resource specified in loc URI query parameter:
mountNi '#{loc}'
