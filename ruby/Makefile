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


RUBYSRC=ni.rb chkni map.rb mapdsl.rb mapping.rb mkni mounttab.rb netinf.rb httpcl.rb nitowellknown niutils.rb pubni regni routedsl.rb routes.rb routing.rb searchni tabentry.rb testni.rb testudp.rb udpcl.rb digest-trunc.rb ni2bin ni2nih ni2qr nih2ni 
#utils.rb ## rdoc has issues with this

.PHONY: testudp test doc clean splash

splash:
	@echo "run 'make doc' to create documention, or 'make test' to run the tests"

doc:
	-rdoc -d $(RUBYSRC) README


test:
	ruby testni.rb

testudp:
	ruby testudp.rb


clean:
	rm -rf *~ doc

