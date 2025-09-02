// Wrapper around shared implementation specifying unstructured probability = 20 (mostly structured)
#ifndef _NosepokeStrucImpureMachine_h
#define _NosepokeStrucImpureMachine_h

#include "NosepokeImpureShared.h"

static NosepokeImpureState NosepokeStrucImpureVar = {0,{0,0},0,0};

inline void NosepokeStrucImpureMachine(){
	const int UNSTRUCTURED_PROB = 20; // 20% unstructured, 80% structured
	RunNosepokeImpureMachine(NosepokeStrucImpureVar, UNSTRUCTURED_PROB);
}

#endif


