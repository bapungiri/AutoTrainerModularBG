#ifndef _NosepokeUnstrucImpureMachine_h
#define _NosepokeUnstrucImpureMachine_h

#include "NosepokeImpureShared.h"

static NosepokeImpureState NosepokeUnstrucImpureVar = {0,{0,0},0,0};

inline void NosepokeUnstrucImpureMachine(){
	const int UNSTRUCTURED_PROB = 80; // 80% unstructured environment probability
	RunNosepokeImpureMachine(NosepokeUnstrucImpureVar, UNSTRUCTURED_PROB);
}

#endif

