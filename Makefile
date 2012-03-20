
all: c-dir ruby-dir doxy

doxy: doc/nilib_apis
	doxygen doc/nilib_apis >doxyout 2>&1 

clean: 
	- rm -f doxyout 
	$(MAKE) -C c clean

c-dir: c
	$(MAKE) -C c

ruby-dir: ruby
	#	$(MAKE) -C ruby

