/* nistruct module -- pack values into and (out of) strings */

/* New version supporting byte order, alignment and size options,
 * character strings, and unsigned numbers. Adapted to handle SDNVs 
 * (Self-Defining Numeric Values) as used in the DTN Bundle Protocol
 * in netowrk/big-endian mode only.
 */
   
/******************************************************************************
 * This module is derived from the Modules/_struct.c source in release 2.7.3
 * of Python.  The license for this module is the Python Software License 
 * Version 2 reproduced below.  In line with this licence, the changes to this
 * are described below.
 *
 *   Original code:
 *     Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 
 *                   2011, 2012 Python Software Foundation
 *   Changes:
 *     Copyright (c) 2012 Trinity College Dublin and Folly Consulting Ltd
 * 
 *
 *  PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
 * --------------------------------------------
 * 
 * 1. This LICENSE AGREEMENT is between the Python Software Foundation
 * ("PSF"), and the Individual or Organization ("Licensee") accessing and
 * otherwise using this software ("Python") in source or binary form and
 * its associated documentation.
 * 
 * 2. Subject to the terms and conditions of this License Agreement, PSF hereby
 * grants Licensee a nonexclusive, royalty-free, world-wide license to 
 * reproduce, analyze, test, perform and/or display publicly, prepare 
 * derivative works, distribute, and otherwise use Python alone or in any 
 * derivative version, provided, however, that PSF's License Agreement and 
 * PSF's notice of copyright, i.e., "Copyright (c) 2001, 2002, 2003, 2004, 
 * 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012 Python Software Foundation; 
 * All Rights Reserved" are retained in Python alone or in any derivative 
 * version prepared by Licensee.
 * 
 * 3. In the event Licensee prepares a derivative work that is based on
 * or incorporates Python or any part thereof, and wants to make
 * the derivative work available to others as provided herein, then
 * Licensee hereby agrees to include in any such work a brief summary of
 * the changes made to Python.
 * 
 * 4. PSF is making Python available to Licensee on an "AS IS"
 * basis.  PSF MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
 * IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, PSF MAKES NO AND
 * DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
 * FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON WILL NOT
 * INFRINGE ANY THIRD PARTY RIGHTS.
 * 
 * 5. PSF SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
 * FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS
 * A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON,
 * OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.
 * 
 * 6. This License Agreement will automatically terminate upon a material
 * breach of its terms and conditions.
 * 
 * 7. Nothing in this License Agreement shall be deemed to create any
 * relationship of agency, partnership, or joint venture between PSF and
 * Licensee.  This License Agreement does not grant permission to use PSF
 * trademarks or trade name in a trademark sense to endorse or promote
 * products or services of Licensee, or any third party.
 * 
 * 8. By copying, installing or otherwise using Python, Licensee
 * agrees to be bound by the terms and conditions of this License
 * Agreement.
 ******************************************************************************/
 
 /**
  * Changes for supporting SDNVs
  * ============================
  *
  * The original struct module deals only with fixed sized items in structures
  * This adaptation is intended to allow it to be used with network protocols
  * that contain variable length encoding of integers as described in RFC 6256
  * and used in various DTN protocols including the Bundle Protocol (RFC 5050).
  *
  * With the intention of usage for network protocols rather than in-memory
  * C data structures (as was the intent for the original struct module), SDNV
  * support is only provided for network/big-endian format specifications with
  * no padding.  It is not implemented for native or little-endian operations.
  *
  * Support is provided for up to 64 bit SDNVs that can be handled in 
  * 'long long' type variables in line with the RFC 5050 specifications.
  *
  * The changes made are as follows:
  * - Format code 'v' added to big-endian table
  * - Code 'v' is treated as a new integer format using 'long long' type.
  * - Functions bp_sdnv and bu_sdnv have been added to pack and unpack an SDNV.
  * - To cope with the variable length encoding of SDNVs:
  *   - The 'size' of the format (number of octets needed in packed form)
  *     is calculated as the largest possible size.  This is done by allowing
  *     the 10 octets maximum for each SDNV in the format.
  *   - A corresponding minimum size is recorded allowing one octet per SDNV.
  *   - The destination string for packing is initially allocated to the 
  *     maximum size.
  *   - During packing of SDNVs, the actual amount of space used is recorded
  *     and the unused space notified to the calling routine by overloading
  *     the return code (now either -1 for error, 0 if all allocated space
  *     used (consistent with existing routines), > 0 indicating amount of
  *     unused octets).
  *   - On completion of packing, the string is resized to the exact amount of 
  *     space used using _PyString_Resize - this is legitimate because we are
  *     dealing with a newly created Python string. 
  *   - During unpacking, the input string size is checked to see that it lies 
  *     between the maximum and minimum before starting.  Then the amount of
  *     buffer unpacked is monitored to check we don't run off  the end (note 
  *     that SDNVs will be handily terminated by the trailing Nul character
  *     in the string buffer avoiding the possibility of running off the end
  *     of the buffer).
  *   - The unpack routines now return an extra entry at the beginning of the 
  *     return tuple.  This contains an integer which is the actual number of
  *     octets of the buffer processed during unpacking.
  *   - The amount of the input string that was not used for unpacking an SDNV
  *     as compared with the maximum possible is recorded by the SDNV unpacking
  *     function in a global variable and used to offset the starting position
  *     for future unpacking (apologies - this is hacky but would otherwise
  *     have to alter interfaces of all existing unpack routines - might do 
  *     this later.)
  * - The calcsize method now returns a 2-tuple with the minimum and maximum
  *   sizes of the output string resulting from the format.
  *
      @code
      Revision History
      ================
      Version   Date       Author         Notes
      1.0       30/12/2012 Elwyn Davies   Created from Python 2.7.3 
                                          Modules/_struct.c.
      @endcode
  *****************************************************************************/
   

#define PY_SSIZE_T_CLEAN

#include "Python.h"
#include "structseq.h"
#include "structmember.h"
#include <ctype.h>

static PyTypeObject PyStructType;

/* compatibility macros */
#if (PY_VERSION_HEX < 0x02050000)
typedef int Py_ssize_t;
#endif

/* warning messages */
#define FLOAT_COERCE_WARN "integer argument expected, got float"
#define NON_INTEGER_WARN "integer argument expected, got non-integer " \
    "(implicit conversion using __int__ is deprecated)"
    
/* Minimum and maximum size taken up by an encoded SDNV */
#define SDNV_MIN_LENGTH 1
#define SDNV_MAX_LENGTH 10

/* Maximum number of octets used for SDNV integers */ 
#define SDNV_INT_SIZE 8

/* The translation function for each format character is table driven */
typedef struct _formatdef {
    char format;
    Py_ssize_t size;
    Py_ssize_t alignment;
    PyObject* (*unpack)(const char *,
                        const struct _formatdef *);
    int (*pack)(char *, PyObject *,
                const struct _formatdef *);
} formatdef;

typedef struct _formatcode {
    const struct _formatdef *fmtdef;
    Py_ssize_t offset;
    Py_ssize_t size;
} formatcode;

/* Struct object interface */

typedef struct {
    PyObject_HEAD
    Py_ssize_t s_size_max;
    Py_ssize_t s_size_min;
    Py_ssize_t s_len;
    formatcode *s_codes;
    PyObject *s_format;
    PyObject *weakreflist; /* List of weak references */
} PyStructObject;


#define PyStruct_Check(op) PyObject_TypeCheck(op, &PyStructType)
#define PyStruct_CheckExact(op) (Py_TYPE(op) == &PyStructType)


/* Exception */

static PyObject *StructError;


/* Define various structs to figure out the alignments of types */


typedef struct { char c; short x; } st_short;
typedef struct { char c; int x; } st_int;
typedef struct { char c; long x; } st_long;
typedef struct { char c; float x; } st_float;
typedef struct { char c; double x; } st_double;
typedef struct { char c; void *x; } st_void_p;

#define SHORT_ALIGN (sizeof(st_short) - sizeof(short))
#define INT_ALIGN (sizeof(st_int) - sizeof(int))
#define LONG_ALIGN (sizeof(st_long) - sizeof(long))
#define FLOAT_ALIGN (sizeof(st_float) - sizeof(float))
#define DOUBLE_ALIGN (sizeof(st_double) - sizeof(double))
#define VOID_P_ALIGN (sizeof(st_void_p) - sizeof(void *))

/* We can't support q and Q in native mode unless the compiler does;
   in std mode, they're 8 bytes on all platforms. */
#ifdef HAVE_LONG_LONG
typedef struct { char c; PY_LONG_LONG x; } s_long_long;
#define LONG_LONG_ALIGN (sizeof(s_long_long) - sizeof(PY_LONG_LONG))
#endif

#ifdef HAVE_C99_BOOL
#define BOOL_TYPE _Bool
typedef struct { char c; _Bool x; } s_bool;
#define BOOL_ALIGN (sizeof(s_bool) - sizeof(BOOL_TYPE))
#else
#define BOOL_TYPE char
#define BOOL_ALIGN 0
#endif

/* Note: SDNVs are only supported in network mode (big endian, unpadded) */

#define STRINGIFY(x)    #x

#ifdef __powerc
#pragma options align=reset
#endif

static char *integer_codes = "bBhHiIlLqQv";

/* Helper to get a PyLongObject by hook or by crook.  Caller should decref. */

static PyObject *
get_pylong(PyObject *v)
{
    PyObject *r, *w;
    int converted = 0;
    assert(v != NULL);
    if (!PyInt_Check(v) && !PyLong_Check(v)) {
        PyNumberMethods *m;
        /* Not an integer; first try to use __index__ to
           convert to an integer.  If the __index__ method
           doesn't exist, or raises a TypeError, try __int__.
           Use of the latter is deprecated, and will fail in
           Python 3.x. */

        m = Py_TYPE(v)->tp_as_number;
        if (PyIndex_Check(v)) {
            w = PyNumber_Index(v);
            if (w != NULL) {
                v = w;
                /* successfully converted to an integer */
                converted = 1;
            }
            else if (PyErr_ExceptionMatches(PyExc_TypeError)) {
                PyErr_Clear();
            }
            else
                return NULL;
        }
        if (!converted && m != NULL && m->nb_int != NULL) {
            /* Special case warning message for floats, for
               backwards compatibility. */
            if (PyFloat_Check(v)) {
                if (PyErr_WarnEx(
                            PyExc_DeprecationWarning,
                            FLOAT_COERCE_WARN, 1))
                    return NULL;
            }
            else {
                if (PyErr_WarnEx(
                            PyExc_DeprecationWarning,
                            NON_INTEGER_WARN, 1))
                    return NULL;
            }
            v = m->nb_int(v);
            if (v == NULL)
                return NULL;
            if (!PyInt_Check(v) && !PyLong_Check(v)) {
                PyErr_SetString(PyExc_TypeError,
                                "__int__ method returned "
                                "non-integer");
                return NULL;
            }
            converted = 1;
        }
        if (!converted) {
            PyErr_SetString(StructError,
                            "cannot convert argument "
                            "to integer");
            return NULL;
        }
    }
    else
        /* Ensure we own a reference to v. */
        Py_INCREF(v);

    assert(PyInt_Check(v) || PyLong_Check(v));
    if (PyInt_Check(v)) {
        r = PyLong_FromLong(PyInt_AS_LONG(v));
        Py_DECREF(v);
    }
    else if (PyLong_Check(v)) {
        assert(PyLong_Check(v));
        r = v;
    }
    else {
        r = NULL;   /* silence compiler warning about
                       possibly uninitialized variable */
        assert(0);  /* shouldn't ever get here */
    }

    return r;
}

/* Helper to convert a Python object to a C long.  Sets an exception
   (struct.error for an inconvertible type, OverflowError for
   out-of-range values) and returns -1 on error. */

static int
get_long(PyObject *v, long *p)
{
    long x;

    v = get_pylong(v);
    if (v == NULL)
        return -1;
    assert(PyLong_Check(v));
    x = PyLong_AsLong(v);
    Py_DECREF(v);
    if (x == (long)-1 && PyErr_Occurred())
        return -1;
    *p = x;
    return 0;
}

/* Same, but handling unsigned long */

static int
get_ulong(PyObject *v, unsigned long *p)
{
    unsigned long x;

    v = get_pylong(v);
    if (v == NULL)
        return -1;
    assert(PyLong_Check(v));
    x = PyLong_AsUnsignedLong(v);
    Py_DECREF(v);
    if (x == (unsigned long)-1 && PyErr_Occurred())
        return -1;
    *p = x;
    return 0;
}

#ifdef HAVE_LONG_LONG

/* Same, but handling native long long. */

static int
get_longlong(PyObject *v, PY_LONG_LONG *p)
{
    PY_LONG_LONG x;

    v = get_pylong(v);
    if (v == NULL)
        return -1;
    assert(PyLong_Check(v));
    x = PyLong_AsLongLong(v);
    Py_DECREF(v);
    if (x == (PY_LONG_LONG)-1 && PyErr_Occurred())
        return -1;
    *p = x;
    return 0;
}

/* Same, but handling native unsigned long long. */

static int
get_ulonglong(PyObject *v, unsigned PY_LONG_LONG *p)
{
    unsigned PY_LONG_LONG x;

    v = get_pylong(v);
    if (v == NULL)
        return -1;
    assert(PyLong_Check(v));
    x = PyLong_AsUnsignedLongLong(v);
    Py_DECREF(v);
    if (x == (unsigned PY_LONG_LONG)-1 && PyErr_Occurred())
        return -1;
    *p = x;
    return 0;
}

#endif

/* Floating point helpers */

static PyObject *
unpack_float(const char *p,  /* start of 4-byte string */
         int le)             /* true for little-endian, false for big-endian */
{
    double x;

    x = _PyFloat_Unpack4((unsigned char *)p, le);
    if (x == -1.0 && PyErr_Occurred())
        return NULL;
    return PyFloat_FromDouble(x);
}

static PyObject *
unpack_double(const char *p,  /* start of 8-byte string */
          int le)         /* true for little-endian, false for big-endian */
{
    double x;

    x = _PyFloat_Unpack8((unsigned char *)p, le);
    if (x == -1.0 && PyErr_Occurred())
        return NULL;
    return PyFloat_FromDouble(x);
}

/* Helper to format the range error exceptions */
static int
_range_error(const formatdef *f, int is_unsigned)
{
    /* ulargest is the largest unsigned value with f->size bytes.
     * Note that the simpler:
     *     ((size_t)1 << (f->size * 8)) - 1
     * doesn't work when f->size == sizeof(size_t) because C doesn't
     * define what happens when a left shift count is >= the number of
     * bits in the integer being shifted; e.g., on some boxes it doesn't
     * shift at all when they're equal.
     */
    const size_t ulargest = (size_t)-1 >> ((SIZEOF_SIZE_T - f->size)*8);
    assert(f->size >= 1 && f->size <= SIZEOF_SIZE_T);
    if (is_unsigned)
        PyErr_Format(StructError,
            "'%c' format requires 0 <= number <= %zu",
            f->format,
            ulargest);
    else {
        const Py_ssize_t largest = (Py_ssize_t)(ulargest >> 1);
        PyErr_Format(StructError,
            "'%c' format requires %zd <= number <= %zd",
            f->format,
            ~ largest,
            largest);
    }
    return -1;
}



/* A large number of small routines follow, with names of the form

   [bln][up]_TYPE

   [bln] distiguishes among big-endian, little-endian and native.
   [pu] distiguishes between pack (to struct) and unpack (from struct).
   TYPE is one of char, byte, ubyte, etc.
*/

/* Native mode routines. ****************************************************/
/* NOTE:
   In all n[up]_<type> routines handling types larger than 1 byte, there is
   *no* guarantee that the p pointer is properly aligned for each type,
   therefore memcpy is called.  An intermediate variable is used to
   compensate for big-endian architectures.
   Normally both the intermediate variable and the memcpy call will be
   skipped by C optimisation in little-endian architectures (gcc >= 2.91
   does this). */

static PyObject *
nu_char(const char *p, const formatdef *f)
{
    return PyString_FromStringAndSize(p, 1);
}

static PyObject *
nu_byte(const char *p, const formatdef *f)
{
    return PyInt_FromLong((long) *(signed char *)p);
}

static PyObject *
nu_ubyte(const char *p, const formatdef *f)
{
    return PyInt_FromLong((long) *(unsigned char *)p);
}

static PyObject *
nu_short(const char *p, const formatdef *f)
{
    short x;
    memcpy((char *)&x, p, sizeof x);
    return PyInt_FromLong((long)x);
}

static PyObject *
nu_ushort(const char *p, const formatdef *f)
{
    unsigned short x;
    memcpy((char *)&x, p, sizeof x);
    return PyInt_FromLong((long)x);
}

static PyObject *
nu_int(const char *p, const formatdef *f)
{
    int x;
    memcpy((char *)&x, p, sizeof x);
    return PyInt_FromLong((long)x);
}

static PyObject *
nu_uint(const char *p, const formatdef *f)
{
    unsigned int x;
    memcpy((char *)&x, p, sizeof x);
#if (SIZEOF_LONG > SIZEOF_INT)
    return PyInt_FromLong((long)x);
#else
    if (x <= ((unsigned int)LONG_MAX))
        return PyInt_FromLong((long)x);
    return PyLong_FromUnsignedLong((unsigned long)x);
#endif
}

static PyObject *
nu_long(const char *p, const formatdef *f)
{
    long x;
    memcpy((char *)&x, p, sizeof x);
    return PyInt_FromLong(x);
}

static PyObject *
nu_ulong(const char *p, const formatdef *f)
{
    unsigned long x;
    memcpy((char *)&x, p, sizeof x);
    if (x <= LONG_MAX)
        return PyInt_FromLong((long)x);
    return PyLong_FromUnsignedLong(x);
}

/* Native mode doesn't support q or Q unless the platform C supports
   long long (or, on Windows, __int64). */

#ifdef HAVE_LONG_LONG

static PyObject *
nu_longlong(const char *p, const formatdef *f)
{
    PY_LONG_LONG x;
    memcpy((char *)&x, p, sizeof x);
    if (x >= LONG_MIN && x <= LONG_MAX)
        return PyInt_FromLong(Py_SAFE_DOWNCAST(x, PY_LONG_LONG, long));
    return PyLong_FromLongLong(x);
}

static PyObject *
nu_ulonglong(const char *p, const formatdef *f)
{
    unsigned PY_LONG_LONG x;
    memcpy((char *)&x, p, sizeof x);
    if (x <= LONG_MAX)
        return PyInt_FromLong(Py_SAFE_DOWNCAST(x, unsigned PY_LONG_LONG, long));
    return PyLong_FromUnsignedLongLong(x);
}

#endif

static PyObject *
nu_bool(const char *p, const formatdef *f)
{
    BOOL_TYPE x;
    memcpy((char *)&x, p, sizeof x);
    return PyBool_FromLong(x != 0);
}


static PyObject *
nu_float(const char *p, const formatdef *f)
{
    float x;
    memcpy((char *)&x, p, sizeof x);
    return PyFloat_FromDouble((double)x);
}

static PyObject *
nu_double(const char *p, const formatdef *f)
{
    double x;
    memcpy((char *)&x, p, sizeof x);
    return PyFloat_FromDouble(x);
}

static PyObject *
nu_void_p(const char *p, const formatdef *f)
{
    void *x;
    memcpy((char *)&x, p, sizeof x);
    return PyLong_FromVoidPtr(x);
}

static int
np_byte(char *p, PyObject *v, const formatdef *f)
{
    long x;
    if (get_long(v, &x) < 0)
        return -1;
    if (x < -128 || x > 127){
        PyErr_SetString(StructError,
                        "byte format requires -128 <= number <= 127");
        return -1;
    }
    *p = (char)x;
    return 0;
}

static int
np_ubyte(char *p, PyObject *v, const formatdef *f)
{
    long x;
    if (get_long(v, &x) < 0)
        return -1;
    if (x < 0 || x > 255){
        PyErr_SetString(StructError,
                        "ubyte format requires 0 <= number <= 255");
        return -1;
    }
    *p = (char)x;
    return 0;
}

static int
np_char(char *p, PyObject *v, const formatdef *f)
{
    if (!PyString_Check(v) || PyString_Size(v) != 1) {
        PyErr_SetString(StructError,
                        "char format require string of length 1");
        return -1;
    }
    *p = *PyString_AsString(v);
    return 0;
}

static int
np_short(char *p, PyObject *v, const formatdef *f)
{
    long x;
    short y;
    if (get_long(v, &x) < 0)
        return -1;
    if (x < SHRT_MIN || x > SHRT_MAX){
        PyErr_SetString(StructError,
                        "short format requires " STRINGIFY(SHRT_MIN)
                        " <= number <= " STRINGIFY(SHRT_MAX));
        return -1;
    }
    y = (short)x;
    memcpy(p, (char *)&y, sizeof y);
    return 0;
}

static int
np_ushort(char *p, PyObject *v, const formatdef *f)
{
    long x;
    unsigned short y;
    if (get_long(v, &x) < 0)
        return -1;
    if (x < 0 || x > USHRT_MAX){
        PyErr_SetString(StructError,
                        "ushort format requires 0 <= number <= " STRINGIFY(USHRT_MAX));
        return -1;
    }
    y = (unsigned short)x;
    memcpy(p, (char *)&y, sizeof y);
    return 0;
}

static int
np_int(char *p, PyObject *v, const formatdef *f)
{
    long x;
    int y;
    if (get_long(v, &x) < 0)
        return -1;
#if (SIZEOF_LONG > SIZEOF_INT)
    if ((x < ((long)INT_MIN)) || (x > ((long)INT_MAX)))
        return _range_error(f, 0);
#endif
    y = (int)x;
    memcpy(p, (char *)&y, sizeof y);
    return 0;
}

static int
np_uint(char *p, PyObject *v, const formatdef *f)
{
    unsigned long x;
    unsigned int y;
    if (get_ulong(v, &x) < 0)
        return -1;
    y = (unsigned int)x;
#if (SIZEOF_LONG > SIZEOF_INT)
    if (x > ((unsigned long)UINT_MAX))
        return _range_error(f, 1);
#endif
    memcpy(p, (char *)&y, sizeof y);
    return 0;
}

static int
np_long(char *p, PyObject *v, const formatdef *f)
{
    long x;
    if (get_long(v, &x) < 0)
        return -1;
    memcpy(p, (char *)&x, sizeof x);
    return 0;
}

static int
np_ulong(char *p, PyObject *v, const formatdef *f)
{
    unsigned long x;
    if (get_ulong(v, &x) < 0)
        return -1;
    memcpy(p, (char *)&x, sizeof x);
    return 0;
}

#ifdef HAVE_LONG_LONG

static int
np_longlong(char *p, PyObject *v, const formatdef *f)
{
    PY_LONG_LONG x;
    if (get_longlong(v, &x) < 0)
        return -1;
    memcpy(p, (char *)&x, sizeof x);
    return 0;
}

static int
np_ulonglong(char *p, PyObject *v, const formatdef *f)
{
    unsigned PY_LONG_LONG x;
    if (get_ulonglong(v, &x) < 0)
        return -1;
    memcpy(p, (char *)&x, sizeof x);
    return 0;
}
#endif


static int
np_bool(char *p, PyObject *v, const formatdef *f)
{
    int y;
    BOOL_TYPE x;
    y = PyObject_IsTrue(v);
    if (y < 0)
        return -1;
    x = y;
    memcpy(p, (char *)&x, sizeof x);
    return 0;
}

static int
np_float(char *p, PyObject *v, const formatdef *f)
{
    float x = (float)PyFloat_AsDouble(v);
    if (x == -1 && PyErr_Occurred()) {
        PyErr_SetString(StructError,
                        "required argument is not a float");
        return -1;
    }
    memcpy(p, (char *)&x, sizeof x);
    return 0;
}

static int
np_double(char *p, PyObject *v, const formatdef *f)
{
    double x = PyFloat_AsDouble(v);
    if (x == -1 && PyErr_Occurred()) {
        PyErr_SetString(StructError,
                        "required argument is not a float");
        return -1;
    }
    memcpy(p, (char *)&x, sizeof(double));
    return 0;
}

static int
np_void_p(char *p, PyObject *v, const formatdef *f)
{
    void *x;

    v = get_pylong(v);
    if (v == NULL)
        return -1;
    assert(PyLong_Check(v));
    x = PyLong_AsVoidPtr(v);
    Py_DECREF(v);
    if (x == NULL && PyErr_Occurred())
        return -1;
    memcpy(p, (char *)&x, sizeof x);
    return 0;
}

static formatdef native_table[] = {
    {'x',       sizeof(char),   0,              NULL},
    {'b',       sizeof(char),   0,              nu_byte,        np_byte},
    {'B',       sizeof(char),   0,              nu_ubyte,       np_ubyte},
    {'c',       sizeof(char),   0,              nu_char,        np_char},
    {'s',       sizeof(char),   0,              NULL},
    {'p',       sizeof(char),   0,              NULL},
    {'h',       sizeof(short),  SHORT_ALIGN,    nu_short,       np_short},
    {'H',       sizeof(short),  SHORT_ALIGN,    nu_ushort,      np_ushort},
    {'i',       sizeof(int),    INT_ALIGN,      nu_int,         np_int},
    {'I',       sizeof(int),    INT_ALIGN,      nu_uint,        np_uint},
    {'l',       sizeof(long),   LONG_ALIGN,     nu_long,        np_long},
    {'L',       sizeof(long),   LONG_ALIGN,     nu_ulong,       np_ulong},
#ifdef HAVE_LONG_LONG
    {'q',       sizeof(PY_LONG_LONG), LONG_LONG_ALIGN, nu_longlong, np_longlong},
    {'Q',       sizeof(PY_LONG_LONG), LONG_LONG_ALIGN, nu_ulonglong,np_ulonglong},
#endif
    {'?',       sizeof(BOOL_TYPE),      BOOL_ALIGN,     nu_bool,        np_bool},
    {'f',       sizeof(float),  FLOAT_ALIGN,    nu_float,       np_float},
    {'d',       sizeof(double), DOUBLE_ALIGN,   nu_double,      np_double},
    {'P',       sizeof(void *), VOID_P_ALIGN,   nu_void_p,      np_void_p},
    {0}
};

/* Big-endian routines. *****************************************************/

static PyObject *
bu_int(const char *p, const formatdef *f)
{
    long x = 0;
    Py_ssize_t i = f->size;
    const unsigned char *bytes = (const unsigned char *)p;
    do {
        x = (x<<8) | *bytes++;
    } while (--i > 0);
    /* Extend the sign bit. */
    if (SIZEOF_LONG > f->size)
        x |= -(x & (1L << ((8 * f->size) - 1)));
    return PyInt_FromLong(x);
}

static PyObject *
bu_uint(const char *p, const formatdef *f)
{
    unsigned long x = 0;
    Py_ssize_t i = f->size;
    const unsigned char *bytes = (const unsigned char *)p;
    do {
        x = (x<<8) | *bytes++;
    } while (--i > 0);
    if (x <= LONG_MAX)
        return PyInt_FromLong((long)x);
    return PyLong_FromUnsignedLong(x);
}

static PyObject *
bu_longlong(const char *p, const formatdef *f)
{
#ifdef HAVE_LONG_LONG
    PY_LONG_LONG x = 0;
    Py_ssize_t i = f->size;
    const unsigned char *bytes = (const unsigned char *)p;
    do {
        x = (x<<8) | *bytes++;
    } while (--i > 0);
    /* Extend the sign bit. */
    if (SIZEOF_LONG_LONG > f->size)
        x |= -(x & ((PY_LONG_LONG)1 << ((8 * f->size) - 1)));
    if (x >= LONG_MIN && x <= LONG_MAX)
        return PyInt_FromLong(Py_SAFE_DOWNCAST(x, PY_LONG_LONG, long));
    return PyLong_FromLongLong(x);
#else
    return _PyLong_FromByteArray((const unsigned char *)p,
                                  8,
                                  0, /* little-endian */
                      1  /* signed */);
#endif
}

static PyObject *
bu_ulonglong(const char *p, const formatdef *f)
{
#ifdef HAVE_LONG_LONG
    unsigned PY_LONG_LONG x = 0;
    Py_ssize_t i = f->size;
    const unsigned char *bytes = (const unsigned char *)p;
    do {
        x = (x<<8) | *bytes++;
    } while (--i > 0);
    if (x <= LONG_MAX)
        return PyInt_FromLong(Py_SAFE_DOWNCAST(x, unsigned PY_LONG_LONG, long));
    return PyLong_FromUnsignedLongLong(x);
#else
    return _PyLong_FromByteArray((const unsigned char *)p,
                                  8,
                                  0, /* little-endian */
                      0  /* signed */);
#endif
}

static PyObject *
bu_float(const char *p, const formatdef *f)
{
    return unpack_float(p, 0);
}

static PyObject *
bu_double(const char *p, const formatdef *f)
{
    return unpack_double(p, 0);
}

static PyObject *
bu_bool(const char *p, const formatdef *f)
{
    char x;
    memcpy((char *)&x, p, sizeof x);
    return PyBool_FromLong(x != 0);
}

static int
bp_int(char *p, PyObject *v, const formatdef *f)
{
    long x;
    Py_ssize_t i;
    if (get_long(v, &x) < 0)
        return -1;
    i = f->size;
    if (i != SIZEOF_LONG) {
        if ((i == 2) && (x < -32768 || x > 32767))
            return _range_error(f, 0);
#if (SIZEOF_LONG != 4)
        else if ((i == 4) && (x < -2147483648L || x > 2147483647L))
            return _range_error(f, 0);
#endif
    }
    do {
        p[--i] = (char)x;
        x >>= 8;
    } while (i > 0);
    return 0;
}

static int
bp_uint(char *p, PyObject *v, const formatdef *f)
{
    unsigned long x;
    Py_ssize_t i;
    if (get_ulong(v, &x) < 0)
        return -1;
    i = f->size;
    if (i != SIZEOF_LONG) {
        unsigned long maxint = 1;
        maxint <<= (unsigned long)(i * 8);
        if (x >= maxint)
            return _range_error(f, 1);
    }
    do {
        p[--i] = (char)x;
        x >>= 8;
    } while (i > 0);
    return 0;
}

static int
bp_longlong(char *p, PyObject *v, const formatdef *f)
{
    int res;
    unsigned char buf[SDNV_MAX_LENGTH + 1];
    
    v = get_pylong(v);
    if (v == NULL)
        return -1;
    res = _PyLong_AsByteArray((PyLongObject *)v,
                              (unsigned char *)p,
                              8,
                              0, /* little_endian */
                              0  /* unsigned */);
    Py_DECREF(v);
    return res;
}

static int
bp_ulonglong(char *p, PyObject *v, const formatdef *f)
{
    int res;
    v = get_pylong(v);
    if (v == NULL)
        return -1;
    res = _PyLong_AsByteArray((PyLongObject *)v,
                              (unsigned char *)p,
                              8,
                              0, /* little_endian */
                  0  /* signed */);
    Py_DECREF(v);
    return res;
}

static int
bp_float(char *p, PyObject *v, const formatdef *f)
{
    double x = PyFloat_AsDouble(v);
    if (x == -1 && PyErr_Occurred()) {
        PyErr_SetString(StructError,
                        "required argument is not a float");
        return -1;
    }
    return _PyFloat_Pack4(x, (unsigned char *)p, 0);
}

static int
bp_double(char *p, PyObject *v, const formatdef *f)
{
    double x = PyFloat_AsDouble(v);
    if (x == -1 && PyErr_Occurred()) {
        PyErr_SetString(StructError,
                        "required argument is not a float");
        return -1;
    }
    return _PyFloat_Pack8(x, (unsigned char *)p, 0);
}

static int
bp_bool(char *p, PyObject *v, const formatdef *f)
{
    int y;
    y = PyObject_IsTrue(v);
    if (y < 0)
        return -1;
    *p = (char)y;
    return 0;
}

/****************************************************************************/
/**
 * Add SDNV encoding and decoding routines
 */

//----------------------------------------------------------------------
static int
bp_sdnv(char *p, PyObject *v, const formatdef *f)
{
    int res;
    unsigned char high_bit;
    unsigned char *start;
    Py_ssize_t val_len;
    unsigned char buf[SDNV_INT_SIZE];
    unsigned PY_LONG_LONG val, tmp;
    
    memset( buf, 0, SDNV_INT_SIZE);
    v = get_pylong(v);
    if (v == NULL)
        return -1;
    val = PyLong_AsUnsignedLongLong(v);
    Py_DECREF(v);
    start = p;

     /**
      * Figure out how many bytes we need for the encoding.
      */
    val_len = 0;
    tmp = val;

    do {
        tmp = tmp >> 7;
        val_len++;
    } while (tmp != 0);

    assert(val_len > 0);
    assert(val_len <= SDNV_MAX_LENGTH);

    /*
     * Now advance p to the last byte and fill it in backwards with
     * the value bytes.
     */
    p += val_len;
    high_bit = 0; // for the last octet
    do {
        --p;
        *p = (u_char)(high_bit | (val & 0x7f));
        high_bit = (1 << 7); // for all but the last octet
        val = val >> 7;
    } while (val != 0);

    assert(p == start);

    return SDNV_MAX_LENGTH - val_len;
}

//----------------------------------------------------------------------
static Py_ssize_t unused_in_unpack;
static PyObject *
bu_sdnv(const char *p, const formatdef *f)
{
    const char* start = p;   
    unsigned PY_LONG_LONG val;
    Py_ssize_t val_len, octet_count, check;
    
    /*
     * Zero out the result value, then shift in the bytes of the
     * encoding one by one until we hit a byte that has a zero
     * high-order bit.
     */
    octet_count = sizeof(unsigned PY_LONG_LONG);
    //printf("octet count: %d\n", octet_count);
    check = 0xFE << (octet_count - 1) * 8;
    val_len = 0;
    val = 0;
    do {
        if (val_len == SDNV_MAX_LENGTH) {
            //printf("Buffer too short\n");
            return NULL; // buffer too short
        }
        /* Check if any non-zero bits would get shifted out with next shift */
        if ((val & check) != 0) {
            //printf("Overflow\n");
            return NULL; /* there would be overflow */
        }
        //printf("loop\n");
        val = (val << 7) | (*p & 0x7f);
        ++val_len;
        
        if ((*p & (1 << 7)) == 0)
            break; // all done;

        ++p;
    } while (1);
    
    unused_in_unpack += (SDNV_MAX_LENGTH - val_len);

    return PyLong_FromUnsignedLongLong(val);
}
/****************************************************************************/

static formatdef bigendian_table[] = {
    {'x',       1,              0,              NULL},
    {'b',       1,              0,              nu_byte,        np_byte},
    {'B',       1,              0,              nu_ubyte,       np_ubyte},
    {'c',       1,              0,              nu_char,        np_char},
    {'s',       1,              0,              NULL},
    {'p',       1,              0,              NULL},
    {'h',       2,              0,              bu_int,         bp_int},
    {'H',       2,              0,              bu_uint,        bp_uint},
    {'i',       4,              0,              bu_int,         bp_int},
    {'I',       4,              0,              bu_uint,        bp_uint},
    {'l',       4,              0,              bu_int,         bp_int},
    {'L',       4,              0,              bu_uint,        bp_uint},
    {'q',       8,              0,              bu_longlong,    bp_longlong},
    {'Q',       8,              0,              bu_ulonglong,   bp_ulonglong},
    {'?',       1,              0,              bu_bool,        bp_bool},
    {'f',       4,              0,              bu_float,       bp_float},
    {'d',       8,              0,              bu_double,      bp_double},
    {'v',       SDNV_MAX_LENGTH,0,              bu_sdnv,        bp_sdnv},
    {0}
};

/* Little-endian routines. *****************************************************/

static PyObject *
lu_int(const char *p, const formatdef *f)
{
    long x = 0;
    Py_ssize_t i = f->size;
    const unsigned char *bytes = (const unsigned char *)p;
    do {
        x = (x<<8) | bytes[--i];
    } while (i > 0);
    /* Extend the sign bit. */
    if (SIZEOF_LONG > f->size)
        x |= -(x & (1L << ((8 * f->size) - 1)));
    return PyInt_FromLong(x);
}

static PyObject *
lu_uint(const char *p, const formatdef *f)
{
    unsigned long x = 0;
    Py_ssize_t i = f->size;
    const unsigned char *bytes = (const unsigned char *)p;
    do {
        x = (x<<8) | bytes[--i];
    } while (i > 0);
    if (x <= LONG_MAX)
        return PyInt_FromLong((long)x);
    return PyLong_FromUnsignedLong((long)x);
}

static PyObject *
lu_longlong(const char *p, const formatdef *f)
{
#ifdef HAVE_LONG_LONG
    PY_LONG_LONG x = 0;
    Py_ssize_t i = f->size;
    const unsigned char *bytes = (const unsigned char *)p;
    do {
        x = (x<<8) | bytes[--i];
    } while (i > 0);
    /* Extend the sign bit. */
    if (SIZEOF_LONG_LONG > f->size)
        x |= -(x & ((PY_LONG_LONG)1 << ((8 * f->size) - 1)));
    if (x >= LONG_MIN && x <= LONG_MAX)
        return PyInt_FromLong(Py_SAFE_DOWNCAST(x, PY_LONG_LONG, long));
    return PyLong_FromLongLong(x);
#else
    return _PyLong_FromByteArray((const unsigned char *)p,
                                  8,
                                  1, /* little-endian */
                      1  /* signed */);
#endif
}

static PyObject *
lu_ulonglong(const char *p, const formatdef *f)
{
#ifdef HAVE_LONG_LONG
    unsigned PY_LONG_LONG x = 0;
    Py_ssize_t i = f->size;
    const unsigned char *bytes = (const unsigned char *)p;
    do {
        x = (x<<8) | bytes[--i];
    } while (i > 0);
    if (x <= LONG_MAX)
        return PyInt_FromLong(Py_SAFE_DOWNCAST(x, unsigned PY_LONG_LONG, long));
    return PyLong_FromUnsignedLongLong(x);
#else
    return _PyLong_FromByteArray((const unsigned char *)p,
                                  8,
                                  1, /* little-endian */
                      0  /* signed */);
#endif
}

static PyObject *
lu_float(const char *p, const formatdef *f)
{
    return unpack_float(p, 1);
}

static PyObject *
lu_double(const char *p, const formatdef *f)
{
    return unpack_double(p, 1);
}

static int
lp_int(char *p, PyObject *v, const formatdef *f)
{
    long x;
    Py_ssize_t i;
    if (get_long(v, &x) < 0)
        return -1;
    i = f->size;
    if (i != SIZEOF_LONG) {
        if ((i == 2) && (x < -32768 || x > 32767))
            return _range_error(f, 0);
#if (SIZEOF_LONG != 4)
        else if ((i == 4) && (x < -2147483648L || x > 2147483647L))
            return _range_error(f, 0);
#endif
    }
    do {
        *p++ = (char)x;
        x >>= 8;
    } while (--i > 0);
    return 0;
}

static int
lp_uint(char *p, PyObject *v, const formatdef *f)
{
    unsigned long x;
    Py_ssize_t i;
    if (get_ulong(v, &x) < 0)
        return -1;
    i = f->size;
    if (i != SIZEOF_LONG) {
        unsigned long maxint = 1;
        maxint <<= (unsigned long)(i * 8);
        if (x >= maxint)
            return _range_error(f, 1);
    }
    do {
        *p++ = (char)x;
        x >>= 8;
    } while (--i > 0);
    return 0;
}

static int
lp_longlong(char *p, PyObject *v, const formatdef *f)
{
    int res;
    v = get_pylong(v);
    if (v == NULL)
        return -1;
    res = _PyLong_AsByteArray((PyLongObject*)v,
                              (unsigned char *)p,
                              8,
                              1, /* little_endian */
                  1  /* signed */);
    Py_DECREF(v);
    return res;
}

static int
lp_ulonglong(char *p, PyObject *v, const formatdef *f)
{
    int res;
    v = get_pylong(v);
    if (v == NULL)
        return -1;
    res = _PyLong_AsByteArray((PyLongObject*)v,
                              (unsigned char *)p,
                              8,
                              1, /* little_endian */
                  0  /* signed */);
    Py_DECREF(v);
    return res;
}

static int
lp_float(char *p, PyObject *v, const formatdef *f)
{
    double x = PyFloat_AsDouble(v);
    if (x == -1 && PyErr_Occurred()) {
        PyErr_SetString(StructError,
                        "required argument is not a float");
        return -1;
    }
    return _PyFloat_Pack4(x, (unsigned char *)p, 1);
}

static int
lp_double(char *p, PyObject *v, const formatdef *f)
{
    double x = PyFloat_AsDouble(v);
    if (x == -1 && PyErr_Occurred()) {
        PyErr_SetString(StructError,
                        "required argument is not a float");
        return -1;
    }
    return _PyFloat_Pack8(x, (unsigned char *)p, 1);
}

static formatdef lilendian_table[] = {
    {'x',       1,              0,              NULL},
    {'b',       1,              0,              nu_byte,        np_byte},
    {'B',       1,              0,              nu_ubyte,       np_ubyte},
    {'c',       1,              0,              nu_char,        np_char},
    {'s',       1,              0,              NULL},
    {'p',       1,              0,              NULL},
    {'h',       2,              0,              lu_int,         lp_int},
    {'H',       2,              0,              lu_uint,        lp_uint},
    {'i',       4,              0,              lu_int,         lp_int},
    {'I',       4,              0,              lu_uint,        lp_uint},
    {'l',       4,              0,              lu_int,         lp_int},
    {'L',       4,              0,              lu_uint,        lp_uint},
    {'q',       8,              0,              lu_longlong,    lp_longlong},
    {'Q',       8,              0,              lu_ulonglong,   lp_ulonglong},
    {'?',       1,              0,              bu_bool,        bp_bool}, /* Std rep not endian dep,
        but potentially different from native rep -- reuse bx_bool funcs. */
    {'f',       4,              0,              lu_float,       lp_float},
    {'d',       8,              0,              lu_double,      lp_double},
    {0}
};


static const formatdef *
whichtable(char **pfmt)
{
    const char *fmt = (*pfmt)++; /* May be backed out of later */
    switch (*fmt) {
    case '<':
        return lilendian_table;
    case '>':
    case '!': /* Network byte order is big-endian */
        return bigendian_table;
    case '=': { /* Host byte order -- different from native in alignment! */
        int n = 1;
        char *p = (char *) &n;
        if (*p == 1)
            return lilendian_table;
        else
            return bigendian_table;
    }
    default:
        --*pfmt; /* Back out of pointer increment */
        /* Fall through */
    case '@':
        return native_table;
    }
}


/* Get the table entry for a format code */

static const formatdef *
getentry(int c, const formatdef *f)
{
    for (; f->format != '\0'; f++) {
        if (f->format == c) {
            return f;
        }
    }
    PyErr_SetString(StructError, "bad char in struct format");
    return NULL;
}


/* Align a size according to a format code.  Return -1 on overflow. */

static Py_ssize_t
align(Py_ssize_t size, char c, const formatdef *e)
{
    Py_ssize_t extra;

    if (e->format == c) {
        if (e->alignment && size > 0) {
            extra = (e->alignment - 1) - (size - 1) % (e->alignment);
            if (extra > PY_SSIZE_T_MAX - size)
                return -1;
            size += extra;
        }
    }
    return size;
}


/* calculate the size of a format string */

static int
prepare_s(PyStructObject *self)
{
    const formatdef *f;
    const formatdef *e;
    formatcode *codes;

    const char *s;
    const char *fmt;
    char c;
    Py_ssize_t size, len, num, itemsize, sdnv_cnt;

    fmt = PyString_AS_STRING(self->s_format);

    f = whichtable((char **)&fmt);

    s = fmt;
    size = 0;
    len = 0;
    sdnv_cnt = 0;
    while ((c = *s++) != '\0') {
        if (isspace(Py_CHARMASK(c)))
            continue;
        if ('0' <= c && c <= '9') {
            num = c - '0';
            while ('0' <= (c = *s++) && c <= '9') {
                /* overflow-safe version of
                   if (num*10 + (c - '0') > PY_SSIZE_T_MAX) { ... } */
                if (num >= PY_SSIZE_T_MAX / 10 && (
                        num > PY_SSIZE_T_MAX / 10 ||
                        (c - '0') > PY_SSIZE_T_MAX % 10))
                    goto overflow;
                num = num*10 + (c - '0');
            }
            if (c == '\0')
                break;
        }
        else
            num = 1;

        e = getentry(c, f);
        if (e == NULL)
            return -1;

        switch (c) {
            case 'v': sdnv_cnt++; /* fall through */
            case 's': /* fall through */
            case 'p': len++; break;
            case 'x': break;
            default: len += num; break;
        }

        itemsize = e->size;
        size = align(size, c, e);
        if (size == -1)
            goto overflow;

        /* if (size + num * itemsize > PY_SSIZE_T_MAX) { ... } */
        if (num > (PY_SSIZE_T_MAX - size) / itemsize)
            goto overflow;
        size += num * itemsize;
    }

    /* check for overflow */
    if ((len + 1) > (PY_SSIZE_T_MAX / sizeof(formatcode))) {
        PyErr_NoMemory();
        return -1;
    }

    self->s_size_max = size;
    self->s_size_min = size - ((SDNV_MAX_LENGTH - SDNV_MIN_LENGTH) * sdnv_cnt);
    self->s_len = len;
    // printf("max: %ld min: %ld\n", size, self->s_size_min);
    codes = PyMem_MALLOC((len + 1) * sizeof(formatcode));
    if (codes == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    /* Free any s_codes value left over from a previous initialization. */
    if (self->s_codes != NULL)
        PyMem_FREE(self->s_codes);
    self->s_codes = codes;

    s = fmt;
    size = 0;
    while ((c = *s++) != '\0') {
        if (isspace(Py_CHARMASK(c)))
            continue;
        if ('0' <= c && c <= '9') {
            num = c - '0';
            while ('0' <= (c = *s++) && c <= '9')
                num = num*10 + (c - '0');
            if (c == '\0')
                break;
        }
        else
            num = 1;

        e = getentry(c, f);

        size = align(size, c, e);
        if (c == 's' || c == 'p') {
            codes->offset = size;
            codes->size = num;
            codes->fmtdef = e;
            codes++;
            size += num;
        } else if (c == 'x') {
            size += num;
        } else {
            while (--num >= 0) {
                codes->offset = size;
                codes->size = e->size;
                codes->fmtdef = e;
                codes++;
                size += e->size;
            }
        }
    }
    codes->fmtdef = NULL;
    codes->offset = size;
    codes->size = 0;

    return 0;

  overflow:
    PyErr_SetString(StructError,
                    "total struct size too long");
    return -1;
}

static PyObject *
s_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyObject *self;

    assert(type != NULL && type->tp_alloc != NULL);

    self = type->tp_alloc(type, 0);
    if (self != NULL) {
        PyStructObject *s = (PyStructObject*)self;
        Py_INCREF(Py_None);
        s->s_format = Py_None;
        s->s_codes = NULL;
        s->s_size_max = -1;
        s->s_len = -1;
    }
    return self;
}

static int
s_init(PyObject *self, PyObject *args, PyObject *kwds)
{
    PyStructObject *soself = (PyStructObject *)self;
    PyObject *o_format = NULL;
    int ret = 0;
    static char *kwlist[] = {"format", 0};

    assert(PyStruct_Check(self));

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "S:Struct", kwlist,
                                     &o_format))
        return -1;

    Py_INCREF(o_format);
    Py_CLEAR(soself->s_format);
    soself->s_format = o_format;

    ret = prepare_s(soself);
    return ret;
}

static void
s_dealloc(PyStructObject *s)
{
    if (s->weakreflist != NULL)
        PyObject_ClearWeakRefs((PyObject *)s);
    if (s->s_codes != NULL) {
        PyMem_FREE(s->s_codes);
    }
    Py_XDECREF(s->s_format);
    Py_TYPE(s)->tp_free((PyObject *)s);
}

static PyObject *
s_unpack_internal(PyStructObject *soself, char *startfrom, Py_ssize_t buf_len) {
    formatcode *code;
    Py_ssize_t i = 1;
    const char *res;
    size_t last = 0;
    /* Add an extra position to hold the length of the string unpacked */
    PyObject *result = PyTuple_New(soself->s_len + 1);
    if (result == NULL)
        return NULL;
    unused_in_unpack = 0;

    for (code = soself->s_codes; code->fmtdef != NULL; code++) {
        PyObject *v;
        const formatdef *e = code->fmtdef;
        //printf("code: %c, last: %d\n", e->format, last);
        if ((last >= buf_len) && (code->size > 0)) {
            /* Not enough buffer to unpack rest of format from */
            /* Caters for special case of trailing empty string */
            goto fail;
        }
        res = startfrom + code->offset - unused_in_unpack;
        if (e->format == 's') {
            v = PyString_FromStringAndSize(res, code->size);
        } else if (e->format == 'p') {
            Py_ssize_t n = *(unsigned char*)res;
            if (n >= code->size)
                n = code->size - 1;
            v = PyString_FromStringAndSize(res + 1, n);
        } else {
            v = e->unpack(res, e);
        }
        if (v == NULL)
            goto fail;
        last = code->offset - unused_in_unpack + code->size; 
        PyTuple_SET_ITEM(result, i++, v);
    }
    PyTuple_SET_ITEM(result, 0, PyInt_FromSize_t(last));

    return result;
fail:
    Py_DECREF(result);
    return NULL;
}


PyDoc_STRVAR(s_unpack__doc__,
"S.unpack(str) -> (v1, v2, ...)\n\
\n\
Return tuple containing values unpacked according to this Struct's format.\n\
Requires len(str) == self.size. See struct.__doc__ for more on format\n\
strings.");

static PyObject *
s_unpack(PyObject *self, PyObject *inputstr)
{
    char *start;
    Py_ssize_t len;
    PyObject *args=NULL, *result;
    PyStructObject *soself = (PyStructObject *)self;
    assert(PyStruct_Check(self));
    assert(soself->s_codes != NULL);
    if (inputstr == NULL)
        goto fail;
    if (PyString_Check(inputstr) &&
        ((len = PyString_GET_SIZE(inputstr)) <= soself->s_size_max) &&
        (len >= soself->s_size_min)) {
            return s_unpack_internal(soself, PyString_AS_STRING(inputstr), len);
    }
    args = PyTuple_Pack(1, inputstr);
    if (args == NULL)
        return NULL;
    if (!PyArg_ParseTuple(args, "s#:unpack", &start, &len))
        goto fail;
    if (!((soself->s_size_max >= len) && (soself->s_size_min <= len))) {
        goto fail;
    }
    result = s_unpack_internal(soself, start, len);
    Py_DECREF(args);
    return result;

fail:
    Py_XDECREF(args);
    PyErr_Format(StructError,
        "unpack requires a string argument of length %zd",
        soself->s_size_max);
    return NULL;
}

PyDoc_STRVAR(s_unpack_from__doc__,
"S.unpack_from(buffer[, offset]) -> (v1, v2, ...)\n\
\n\
Return tuple containing values unpacked according to this Struct's format.\n\
Unlike unpack, unpack_from can unpack values from any object supporting\n\
the buffer API, not just str. Requires len(buffer[offset:]) >= self.size.\n\
See struct.__doc__ for more on format strings.");

static PyObject *
s_unpack_from(PyObject *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"buffer", "offset", 0};
#if (PY_VERSION_HEX < 0x02050000)
    static char *fmt = "z#|i:unpack_from";
#else
    static char *fmt = "z#|n:unpack_from";
#endif
    Py_ssize_t buffer_len = 0, offset = 0;
    char *buffer = NULL;
    PyStructObject *soself = (PyStructObject *)self;
    assert(PyStruct_Check(self));
    assert(soself->s_codes != NULL);

    if (!PyArg_ParseTupleAndKeywords(args, kwds, fmt, kwlist,
                                     &buffer, &buffer_len, &offset))
        return NULL;

    if (buffer == NULL) {
        PyErr_Format(StructError,
            "unpack_from requires a buffer argument");
        return NULL;
    }

    if (offset < 0)
        offset += buffer_len;

    if (offset < 0 || (buffer_len - offset) < soself->s_size_min) {
        PyErr_Format(StructError,
            "unpack_from requires a buffer of at least %zd bytes",
            soself->s_size_min);
        return NULL;
    }
    return s_unpack_internal(soself, buffer + offset, (buffer_len - offset));
}


/*
 * Guts of the pack function.
 *
 * Takes a struct object, a tuple of arguments, and offset in that tuple of
 * argument for where to start processing the arguments for packing, and a
 * character buffer for writing the packed string.  The caller must insure
 * that the buffer may contain the required length for packing the arguments.
 * 0 is returned on success, 1 is returned if there is an error.
 *
 */
static int
s_pack_internal(PyStructObject *soself, PyObject *args, int offset, char* buf, 
                Py_ssize_t *unused)
{
    formatcode *code;
    /* XXX(nnorwitz): why does i need to be a local?  can we use
       the offset parameter or do we need the wider width? */
    Py_ssize_t i, sdnv_shorter, pack_res;
    unsigned char *last, *res;

    memset(buf, '\0', soself->s_size_max);
    i = offset;
    sdnv_shorter = 0;
    
    for (code = soself->s_codes; code->fmtdef != NULL; code++) {
        Py_ssize_t n;
        PyObject *v = PyTuple_GET_ITEM(args, i++);
        const formatdef *e = code->fmtdef;
        res = buf + code->offset - sdnv_shorter;
        last = res + code->size;
        if (e->format == 's') {
            if (!PyString_Check(v)) {
                PyErr_SetString(StructError,
                                "argument for 's' must "
                                "be a string");
                return -1;
            }
            n = PyString_GET_SIZE(v);
            if (n > code->size)
                n = code->size;
            if (n > 0)
                memcpy(res, PyString_AS_STRING(v), n);
        } else if (e->format == 'p') {
            if (!PyString_Check(v)) {
                PyErr_SetString(StructError,
                                "argument for 'p' must "
                                "be a string");
                return -1;
            }
            n = PyString_GET_SIZE(v);
            if (n > (code->size - 1))
                n = code->size - 1;
            if (n > 0)
                memcpy(res + 1, PyString_AS_STRING(v), n);
            if (n > 255)
                n = 255;
            *res = Py_SAFE_DOWNCAST(n, Py_ssize_t, unsigned char);
        } else if ((pack_res = e->pack(res, v, e)) < 0) {
            if (strchr(integer_codes, e->format) != NULL &&
                PyErr_ExceptionMatches(PyExc_OverflowError))
                PyErr_Format(StructError,
                             "integer out of range for "
                             "'%c' format code",
                             e->format);
            return -1;
        } else {
            /**
             * For everything but bp_sdnv pack_res is 0 on success.
             * For SDNVs it is the number of of unused positions in the
             * result string.  Future packing starts earlier than was 
             * originally calculated after SDNVs that aren't full size.
             */ 
            sdnv_shorter += pack_res;
            last -= pack_res;
        }
    }
    
    /* Report unused amount of result string*/
    *unused = sdnv_shorter;
    // for (res = buf; res < last; res++) {
        // printf("%u,\n", (unsigned int)(*res));
    //}

    /* Success */
    return 0;
}


PyDoc_STRVAR(s_pack__doc__,
"S.pack(v1, v2, ...) -> string\n\
\n\
Return a string containing values v1, v2, ... packed according to this\n\
Struct's format. See struct.__doc__ for more on format strings.");

static PyObject *
s_pack(PyObject *self, PyObject *args)
{
    PyStructObject *soself;
    PyObject *result;
    Py_ssize_t unused;

    /* Validate arguments. */
    soself = (PyStructObject *)self;
    assert(PyStruct_Check(self));
    assert(soself->s_codes != NULL);
    if (PyTuple_GET_SIZE(args) != soself->s_len)
    {
        PyErr_Format(StructError,
            "pack requires exactly %zd arguments", soself->s_len);
        return NULL;
    }

    /* Allocate a new string */
    result = PyString_FromStringAndSize((char *)NULL, soself->s_size_max);
    if (result == NULL)
        return NULL;

    /* Call the guts */
    if ( s_pack_internal(soself, args, 0, PyString_AS_STRING(result), &unused) != 0 ) {
        Py_DECREF(result);
        return NULL;
    }
    
    /* Shorten string if necessary */
    if (unused > 0) {
        /* printf("unused: %ld, new length: %ld, refcnt: %ld, is string: %d, interned: %d\n", 
                unused, (soself->s_size_max - unused), 
                Py_REFCNT(result), PyString_Check(result),
                PyString_CHECK_INTERNED(result));
         */
         
        if (_PyString_Resize(&result, (Py_ssize_t)(soself->s_size_max - unused)) < 0 ) {
            return NULL;
        }
    // printf("unused: %d\n", unused);
    
    }
    
    return result;
}

PyDoc_STRVAR(s_pack_into__doc__,
"S.pack_into(buffer, offset, v1, v2, ...)\n\
\n\
Pack the values v1, v2, ... according to this Struct's format, write \n\
the packed bytes into the writable buffer buf starting at offset.  Note\n\
that the offset is not an optional argument.  See struct.__doc__ for \n\
more on format strings.");

static PyObject *
s_pack_into(PyObject *self, PyObject *args)
{
    PyStructObject *soself;
    char *buffer;
    Py_ssize_t buffer_len, offset, unused;

    /* Validate arguments.  +1 is for the first arg as buffer. */
    soself = (PyStructObject *)self;
    assert(PyStruct_Check(self));
    assert(soself->s_codes != NULL);
    if (PyTuple_GET_SIZE(args) != (soself->s_len + 2))
    {
        PyErr_Format(StructError,
                     "pack_into requires exactly %zd arguments",
                     (soself->s_len + 2));
        return NULL;
    }

    /* Extract a writable memory buffer from the first argument */
    if ( PyObject_AsWriteBuffer(PyTuple_GET_ITEM(args, 0),
                                                            (void**)&buffer, &buffer_len) == -1 ) {
        return NULL;
    }
    assert( buffer_len >= 0 );

    /* Extract the offset from the first argument */
    offset = PyInt_AsSsize_t(PyTuple_GET_ITEM(args, 1));
    if (offset == -1 && PyErr_Occurred())
        return NULL;

    /* Support negative offsets. */
    if (offset < 0)
        offset += buffer_len;

    /* Check boundaries */
    if (offset < 0 || (buffer_len - offset) < soself->s_size_max) {
        PyErr_Format(StructError,
                     "pack_into requires a buffer of at least %zd bytes",
                     soself->s_size_max);
        return NULL;
    }

    /* Call the guts */
    if ( s_pack_internal(soself, args, 2, buffer + offset, &unused) != 0 ) {
        return NULL;
    }

    Py_RETURN_NONE;
}

static PyObject *
s_get_format(PyStructObject *self, void *unused)
{
    Py_INCREF(self->s_format);
    return self->s_format;
}

static PyObject *
s_get_size(PyStructObject *self, void *unused)
{
    return PyInt_FromSsize_t(self->s_size_max);
}

/* List of functions */

static struct PyMethodDef s_methods[] = {
    {"pack",            s_pack,         METH_VARARGS, s_pack__doc__},
    {"pack_into",       s_pack_into,    METH_VARARGS, s_pack_into__doc__},
    {"unpack",          s_unpack,       METH_O, s_unpack__doc__},
    {"unpack_from",     (PyCFunction)s_unpack_from, METH_VARARGS|METH_KEYWORDS,
                    s_unpack_from__doc__},
    {NULL,       NULL}          /* sentinel */
};

PyDoc_STRVAR(s__doc__, "Compiled struct object");

#define OFF(x) offsetof(PyStructObject, x)

static PyGetSetDef s_getsetlist[] = {
    {"format", (getter)s_get_format, (setter)NULL, "struct format string", NULL},
    {"size", (getter)s_get_size, (setter)NULL, "struct size in bytes", NULL},
    {NULL} /* sentinel */
};

static
PyTypeObject PyStructType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "Struct",
    sizeof(PyStructObject),
    0,
    (destructor)s_dealloc,      /* tp_dealloc */
    0,                                          /* tp_print */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_compare */
    0,                                          /* tp_repr */
    0,                                          /* tp_as_number */
    0,                                          /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    0,                                          /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    PyObject_GenericGetAttr,            /* tp_getattro */
    PyObject_GenericSetAttr,            /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_WEAKREFS,/* tp_flags */
    s__doc__,                           /* tp_doc */
    0,                                          /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    offsetof(PyStructObject, weakreflist),      /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    0,                                          /* tp_iternext */
    s_methods,                          /* tp_methods */
    NULL,                               /* tp_members */
    s_getsetlist,               /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    0,                                          /* tp_descr_get */
    0,                                          /* tp_descr_set */
    0,                                          /* tp_dictoffset */
    s_init,                             /* tp_init */
    PyType_GenericAlloc,/* tp_alloc */
    s_new,                              /* tp_new */
    PyObject_Del,               /* tp_free */
};


/* ---- Standalone functions  ---- */

#define MAXCACHE 100
static PyObject *cache = NULL;

static PyObject *
cache_struct(PyObject *fmt)
{
    PyObject * s_object;

    if (cache == NULL) {
        cache = PyDict_New();
        if (cache == NULL)
            return NULL;
    }

    s_object = PyDict_GetItem(cache, fmt);
    if (s_object != NULL) {
        Py_INCREF(s_object);
        return s_object;
    }

    s_object = PyObject_CallFunctionObjArgs((PyObject *)(&PyStructType), fmt, NULL);
    if (s_object != NULL) {
        if (PyDict_Size(cache) >= MAXCACHE)
            PyDict_Clear(cache);
        /* Attempt to cache the result */
        if (PyDict_SetItem(cache, fmt, s_object) == -1)
            PyErr_Clear();
    }
    return s_object;
}

PyDoc_STRVAR(clearcache_doc,
"Clear the internal cache.");

static PyObject *
clearcache(PyObject *self)
{
    Py_CLEAR(cache);
    Py_RETURN_NONE;
}

PyDoc_STRVAR(calcsize_doc,
"Return size of C struct described by format string fmt.");

static PyObject *
calcsize(PyObject *self, PyObject *fmt)
{
    Py_ssize_t n, m;
    PyObject *s_object = cache_struct(fmt);
    if (s_object == NULL)
        return NULL;
    n = ((PyStructObject *)s_object)->s_size_max;
    m = ((PyStructObject *)s_object)->s_size_min;
    Py_DECREF(s_object);
    return PyTuple_Pack((Py_ssize_t)2, PyInt_FromSsize_t(m), PyInt_FromSsize_t(n));
}

PyDoc_STRVAR(pack_doc,
"Return string containing values v1, v2, ... packed according to fmt.");

static PyObject *
pack(PyObject *self, PyObject *args)
{
    PyObject *s_object, *fmt, *newargs, *result;
    Py_ssize_t n = PyTuple_GET_SIZE(args);

    if (n == 0) {
        PyErr_SetString(PyExc_TypeError, "missing format argument");
        return NULL;
    }
    fmt = PyTuple_GET_ITEM(args, 0);
    newargs = PyTuple_GetSlice(args, 1, n);
    if (newargs == NULL)
        return NULL;

    s_object = cache_struct(fmt);
    if (s_object == NULL) {
        Py_DECREF(newargs);
        return NULL;
    }
    result = s_pack(s_object, newargs);
    Py_DECREF(newargs);
    Py_DECREF(s_object);
    return result;
}

PyDoc_STRVAR(pack_into_doc,
"Pack the values v1, v2, ... according to fmt.\n\
Write the packed bytes into the writable buffer buf starting at offset.");

static PyObject *
pack_into(PyObject *self, PyObject *args)
{
    PyObject *s_object, *fmt, *newargs, *result;
    Py_ssize_t n = PyTuple_GET_SIZE(args);

    if (n == 0) {
        PyErr_SetString(PyExc_TypeError, "missing format argument");
        return NULL;
    }
    fmt = PyTuple_GET_ITEM(args, 0);
    newargs = PyTuple_GetSlice(args, 1, n);
    if (newargs == NULL)
        return NULL;

    s_object = cache_struct(fmt);
    if (s_object == NULL) {
        Py_DECREF(newargs);
        return NULL;
    }
    result = s_pack_into(s_object, newargs);
    Py_DECREF(newargs);
    Py_DECREF(s_object);
    return result;
}

PyDoc_STRVAR(unpack_doc,
"Unpack the string containing packed C structure data, according to fmt.\n\
Requires len(string) == calcsize(fmt).");

static PyObject *
unpack(PyObject *self, PyObject *args)
{
    PyObject *s_object, *fmt, *inputstr, *result;

    if (!PyArg_UnpackTuple(args, "unpack", 2, 2, &fmt, &inputstr))
        return NULL;

    s_object = cache_struct(fmt);
    if (s_object == NULL)
        return NULL;
    result = s_unpack(s_object, inputstr);
    Py_DECREF(s_object);
    return result;
}

PyDoc_STRVAR(unpack_from_doc,
"Unpack the buffer, containing packed C structure data, according to\n\
fmt, starting at offset. Requires len(buffer[offset:]) >= calcsize(fmt).");

static PyObject *
unpack_from(PyObject *self, PyObject *args, PyObject *kwds)
{
    PyObject *s_object, *fmt, *newargs, *result;
    Py_ssize_t n = PyTuple_GET_SIZE(args);

    if (n == 0) {
        PyErr_SetString(PyExc_TypeError, "missing format argument");
        return NULL;
    }
    fmt = PyTuple_GET_ITEM(args, 0);
    newargs = PyTuple_GetSlice(args, 1, n);
    if (newargs == NULL)
        return NULL;

    s_object = cache_struct(fmt);
    if (s_object == NULL) {
        Py_DECREF(newargs);
        return NULL;
    }
    result = s_unpack_from(s_object, newargs, kwds);
    Py_DECREF(newargs);
    Py_DECREF(s_object);
    return result;
}

static struct PyMethodDef module_functions[] = {
    {"_clearcache",     (PyCFunction)clearcache,        METH_NOARGS,    clearcache_doc},
    {"calcsize",        calcsize,       METH_O, calcsize_doc},
    {"pack",            pack,           METH_VARARGS,   pack_doc},
    {"pack_into",       pack_into,      METH_VARARGS,   pack_into_doc},
    {"unpack",          unpack, METH_VARARGS,   unpack_doc},
    {"unpack_from",     (PyCFunction)unpack_from,
                    METH_VARARGS|METH_KEYWORDS,         unpack_from_doc},
    {NULL,       NULL}          /* sentinel */
};


/* Module initialization */

PyDoc_STRVAR(module_doc,
"Functions to convert between Python values and C structs represented\n\
as Python strings. It uses format strings (explained below) as compact\n\
descriptions of the lay-out of the C structs and the intended conversion\n\
to/from Python values.\n\
\n\
The optional first format char indicates byte order, size and alignment:\n\
  @: native order, size & alignment (default)\n\
  =: native order, std. size & alignment\n\
  <: little-endian, std. size & alignment\n\
  >: big-endian, std. size & alignment\n\
  !: same as >\n\
\n\
The remaining chars indicate types of args and must match exactly;\n\
these can be preceded by a decimal repeat count:\n\
  x: pad byte (no data); c:char; b:signed byte; B:unsigned byte;\n\
  ?: _Bool (requires C99; if not available, char is used instead)\n\
  h:short; H:unsigned short; i:int; I:unsigned int;\n\
  l:long; L:unsigned long; f:float; d:double.\n\
Special cases (preceding decimal count indicates length):\n\
  s:string (array of char); p: pascal string (with count byte).\n\
Special case (only available in native format):\n\
  P:an integer type that is wide enough to hold a pointer.\n\
Special case (not in native mode unless 'long long' in platform C):\n\
  q:long long; Q:unsigned long long\n\
Whitespace between formats is ignored.\n\
\n\
The variable struct.error is an exception raised on errors.\n");

PyMODINIT_FUNC
init_nistruct(void)
{
    PyObject *ver, *m;

    ver = PyString_FromString("0.2");
    if (ver == NULL)
        return;

    m = Py_InitModule3("_nistruct", module_functions, module_doc);
    if (m == NULL)
        return;

    Py_TYPE(&PyStructType) = &PyType_Type;
    if (PyType_Ready(&PyStructType) < 0)
        return;

    /* This speed trick can't be used until overflow masking goes
       away, because native endian always raises exceptions
       instead of overflow masking. */

    /* Check endian and swap in faster functions */
    {
        int one = 1;
        formatdef *native = native_table;
        formatdef *other, *ptr;
        if ((int)*(unsigned char*)&one)
            other = lilendian_table;
        else
            other = bigendian_table;
        /* Scan through the native table, find a matching
           entry in the endian table and swap in the
           native implementations whenever possible
           (64-bit platforms may not have "standard" sizes) */
        while (native->format != '\0' && other->format != '\0') {
            ptr = other;
            while (ptr->format != '\0') {
                if (ptr->format == native->format) {
                    /* Match faster when formats are
                       listed in the same order */
                    if (ptr == other)
                        other++;
                    /* Only use the trick if the
                       size matches */
                    if (ptr->size != native->size)
                        break;
                    /* Skip float and double, could be
                       "unknown" float format */
                    if (ptr->format == 'd' || ptr->format == 'f')
                        break;
                    ptr->pack = native->pack;
                    ptr->unpack = native->unpack;
                    break;
                }
                ptr++;
            }
            native++;
        }
    }

    /* Add some symbolic constants to the module */
    if (StructError == NULL) {
        StructError = PyErr_NewException("nistruct.struct_error", NULL, NULL);
        if (StructError == NULL)
            return;
    }

    Py_INCREF(StructError);
    PyModule_AddObject(m, "struct_error", StructError);

    Py_INCREF((PyObject*)&PyStructType);
    PyModule_AddObject(m, "Struct", (PyObject*)&PyStructType);

    PyModule_AddObject(m, "__version__", ver);

    PyModule_AddIntConstant(m, "_PY_STRUCT_RANGE_CHECKING", 1);
    PyModule_AddIntConstant(m, "_PY_STRUCT_FLOAT_COERCE", 1);
}


