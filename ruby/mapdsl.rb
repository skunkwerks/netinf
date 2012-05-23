#
# DSL for NI mapping table
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


require 'mapping'
require 'mounttab'


# This file defines a DSL that can be used to configure NI mappings. See map.rb for an example.

#mapNi will map the specified resource to an NI name and make this
#available. You have to specify the resource identifier (HTTP URI or
#file URI), the authority (can be empty string), and you can
#optionally specify options (see examples in map.rb).
def mapNi(uri, auth, opts=nil)
  Mapping.instance.add(uri,auth, opts)
end

# construct a file URI. To be used in mapping statements.
def fileUri(f)
  "file://" + f.gsub(" ", "%20")
end

# construct a file URI with an absolute path for the specified file
# name. To be used in mapping statements.
def localFile(f)
  fileUri(File::absolute_path(f))
end

#mountNi will install a mapping that is transforming the NI URI to
#another URI (HTTP URI or file URI). The transformation specification
#will be executed in the context of the NI object, i.e., you can use
#NI member functions to access URI elements.
def mountNi(mountString)
  MountTab.instance.add(mountString)
end
