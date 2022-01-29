#ifndef Py_STATICINIT_H
#define Py_STATICINIT_H

#include "object.h"
#include "import.h"

#define NUITKA_PYTHON_STATIC

#if defined(Py_BUILD_CORE) && !defined(Py_BUILD_CORE_MODULE)
#ifdef __cplusplus
extern "C" {
#endif

#ifdef __cplusplus
}
#endif // __cplusplus

static inline void Py_InitStaticModules(void) {
}

#endif

#endif // !Py_STATICINIT_H
