
all: c-dir ruby-dir test-dir

doxy: doc/nilib_apis
	doxygen doc/nilib_apis >doxyout 2>&1 

pydoxy: python/python_apis
	cd python; doxygen python_apis >pydoxyout 2>&1

clean: 
	- rm -f doxyout python/pydoxyout 
	$(MAKE) -C c clean

c-dir: c
	$(MAKE) -C c

ruby-dir: ruby
	#	$(MAKE) -C ruby

test-dir: c-dir 
	cd test; ./doit

