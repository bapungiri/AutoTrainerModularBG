// Unified Nosepoke Impure state machine (structured/unstructured mix)
// Set g_unstructuredProbSetting (0-100) before running to control proportion of unstructured (independent) blocks.

#ifndef _NosepokeImpureMachine_h
#define _NosepokeImpureMachine_h

struct NosepokeImpureState {
  int rewardCounter;
  int probArray[2];
  int blockNum;
  int trialCounter;
  int unstructuredProb;
  uint64_t sessionStartMs;
};

static void updateRewProbGeneric(NosepokeImpureState &st, int unstrProb){
  unsigned int randomEnvDraw = random(100);
  int prob1 = DrawAProb();
  int prob2 = (randomEnvDraw < (unsigned)unstrProb) ? DrawIndependentPair(prob1)
                                                   : DrawDependentPair(prob1);
  st.probArray[0] = prob1;
  st.probArray[1] = prob2;
}

static void reportProbGeneric(const NosepokeImpureState &st){
  float ports[] = {1.0, 2.0};
  for (int i=0;i<2;++i) ReportData(83, (int)ports[i], st.probArray[i]);
}

static int changeBlockGeneric(const NosepokeImpureState &st){
  const int min_length = 100;
  const int switchProb = 2;
  if (st.trialCounter >= min_length && random(100) < (unsigned)switchProb){
    ReportData(111, st.trialCounter, (millis()-stateMachineStartTime));
    ReportData(121, st.blockNum, (millis()-stateMachineStartTime));
    return 1;
  }
  return 0;
}

static int checkSMStateStopGeneric(const NosepokeImpureState &st){
  if (stateStop){
    ReportData(111, st.trialCounter, (millis()-stateMachineStartTime));
    ReportData(121, st.blockNum, (millis()-stateMachineStartTime));
    ReportData(63, st.rewardCounter, (millis()-stateMachineStartTime));
    EndCurrentStateMachine();
    RunStartANDEndStateMachine(&endStateMachine);
    EndCurrentTrainingProtocol();
    return 1;
  }
  return 0;
}

inline void RunNosepokeImpureCore(NosepokeImpureState &st, int unstrProb){
  st.unstructuredProb = unstrProb;
  RunStartANDEndStateMachine(&startStateMachine);
  InitializeStateMachine();
  if (st.sessionStartMs == 0) st.sessionStartMs = epochMillis();
  const unsigned long SESSION_LIMIT_MS = 40UL*60UL*1000UL;
  while (!stateStop){
    uint64_t blockStartTime = epochMillis();
    st.blockNum++; st.trialCounter = 0; st.rewardCounter = 0;
    updateRewProbGeneric(st, unstrProb);
    reportProbGeneric(st);
    int n=0; int rewardPercent=0;
    while (!stateStop){
      if ((epochMillis()-st.sessionStartMs) >= SESSION_LIMIT_MS) { stateStop = 1; }
      HouseKeeping();
      if (checkSMStateStopGeneric(st)) return;
      if (Nosepoke1DI.isOn() || Nosepoke2DI.isOn()){
        uint64_t trialStartTime = epochMillis();
        unsigned int whenNosepoke = (millis()-stateMachineStartTime);
        uint8_t recordNosepoke[2] = {Nosepoke1DI.diRead(), Nosepoke2DI.diRead()};
        int whichnosepoke[2] = {1,2};
        for (int i=0;i<2;++i) if (recordNosepoke[i]) n = whichnosepoke[i];
        WhichNosepoke(whenNosepoke);
        rewardPercent = st.probArray[n-1];
        ReportData(88, rewardPercent,(millis()-stateMachineStartTime));
        bool rewardFlag=false; SpeakerPwdAO.on(50); delayHK(500); SpeakerPwdAO.off(0);
        unsigned long lickWindowStart = millis(); bool lickDetected=false;
        while ((millis()-lickWindowStart)<=5000){
          HouseKeeping(); if (stateStop || checkSMStateStopGeneric(st)){ lickDetected=false; break; }
          if (LickDI.isOn()){ lickDetected=true; LickDI.clear(); st.trialCounter++; unsigned int r=random(100);
            if (r < (unsigned)rewardPercent){ GiveReward(1); rewardFlag=true; st.rewardCounter++; }
            else ReportData(-51,0,(millis()-stateMachineStartTime)); break; }
        }
        if (!lickDetected) ReportData(-52,0,(millis()-stateMachineStartTime));
        if (!rewardFlag) ReportData(86,1,(millis()-stateMachineStartTime));
        uint64_t trialEndTime = epochMillis();
        if (lickDetected) ReportTrialSummary(200, st.probArray[0], st.probArray[1], rewardFlag?1:0,
          st.trialCounter, st.blockNum, st.unstructuredProb, (unsigned long)st.sessionStartMs,
          (unsigned long)blockStartTime, (unsigned long)trialStartTime, (unsigned long)trialEndTime);
        else ReportTrialSummary(201, st.probArray[0], st.probArray[1], -1,
          st.trialCounter, st.blockNum, st.unstructuredProb, (unsigned long)st.sessionStartMs,
          (unsigned long)blockStartTime, (unsigned long)trialStartTime, (unsigned long)trialEndTime);
        if (changeBlockGeneric(st)) break; }
    }
    if (stateStop) break; }
  checkSMStateStopGeneric(st);
}

// Inline configurable probability (requires C++17 for single definition across TUs)
inline int g_unstructuredProbSetting = 80; // default
static NosepokeImpureState g_nosepokeImpureState = {0,{0,0},0,0,0,0};

inline void NosepokeImpureMachine(){
  RunNosepokeImpureCore(g_nosepokeImpureState, g_unstructuredProbSetting);
}

#endif
