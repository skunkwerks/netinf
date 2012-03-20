
all: test nicl send_request libnic.so put_object

clean: 
	- rm -f test.o ni.o nic.o test nicl.o nicl send_request send_request.a libnic.so

nicl: nicl.o ni.o 
	g++ -g -o nicl nicl.o ni.o -lssl

test: test.o ni.o 
	g++ -g -o test test.o ni.o -lssl

ni.o: ni.cc ni.h
	g++ -g -c ni.cc

# Compile as C for use with C programs
libnic.so: ni.cc ni.h
	gcc -x c -fPIC -shared -Wl,-soname,libnic.so -o libnic.so ni.cc

mime.o: mime.cc ni.h
	g++ -g -c mime.cc

mime: mime.o ni.o 
	g++ -g -o mime mime.o ni.o -lssl -lmimetic

test.o: test.cc ni.h
	g++ -g -c test.cc

nicl.o: nicl.cc ni.h
	g++ -g -c nicl.cc

send_request.o: send_request.cc ni.h
	g++ -Wall -g -c send_request.cc -o send_request.o

send_request: send_request.o ni.o
	g++ -Wall -g -o send_request send_request.o ni.o -lssl

put_object.o: put_object.cc ni.h
	g++ -Wall -g -c put_object.cc -o put_object.o

put_object: put_object.o ni.o
	g++ -Wall -g -o put_object put_object.o ni.o -lssl
