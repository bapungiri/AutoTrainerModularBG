// Shared implementation for Struc/Unstruc Impure nosepoke state machines.
// Additional wrapper headers call RunNosepokeImpureMachine with desired value.

#ifndef _NosepokeImpureMachine_h
#define _NosepokeImpureMachine_h

struct NosepokeImpureStruct
{
    int rewardCounter;       // rewards delivered in current block
    int probArray[2];        // current port reward probabilities
    int blockNum;            // block index
    int trialCounter;        // lick-count trials (increment on lick only)
    int unstructuredProb;    // probability (%) of drawing unstructured pair for this animal
    uint64_t sessionStartMs; // session start epoch ms (per animal instance)
};

static void updateRewProbGeneric(NosepokeImpureStruct &st, int unstrProb)
{
    unsigned int randomEnvDraw = random(100);
    int prob1 = DrawAProb();
    int prob2;
    if (randomEnvDraw < (unsigned)unstrProb)
    {
        prob2 = DrawIndependentPair(prob1); // unstructured: independent sampling
    }
    else
    {
        prob2 = DrawDependentPair(prob1); // structured: complementary probabilities
    }
    st.probArray[0] = prob1;
    st.probArray[1] = prob2;
}

static void reportProbGeneric(const NosepokeImpureStruct &st)
{
    float ports[] = {1.0, 2.0};
    for (int i = 0; i < 2; ++i)
    {
        ReportData(83, (int)ports[i], st.probArray[i]);
    }
}

static int changeBlockGeneric(const NosepokeImpureStruct &st)
{
    const int min_length = 100; // minimum lick trials before allowing switch
    const int switchProb = 2;   // percent chance after minimum
    if (st.trialCounter >= min_length)
    {
        unsigned int randomDraw = random(100);
        if (randomDraw < (unsigned)switchProb)
        {
            ReportData(111, st.trialCounter, (millis() - stateMachineStartTime));
            ReportData(121, st.blockNum, (millis() - stateMachineStartTime));
            return 1;
        }
    }
    return 0;
}

static int checkSMStateStopGeneric(const NosepokeImpureState &st)
{
    if (stateStop)
    {
        ReportData(111, st.trialCounter, (millis() - stateMachineStartTime));
        ReportData(121, st.blockNum, (millis() - stateMachineStartTime));
        ReportData(63, st.rewardCounter, (millis() - stateMachineStartTime));
        EndCurrentStateMachine();
        RunStartANDEndStateMachine(&endStateMachine);
        EndCurrentTrainingProtocol();
        return 1;
    }
    return 0;
}

inline void NosepokeImpureMachine(NosepokeImpureStruct &st, int unstrProb)
{
    st.unstructuredProb = unstrProb; // store for logging
    RunStartANDEndStateMachine(&startStateMachine);
    InitializeStateMachine();
    if (st.sessionStartMs == 0)
        st.sessionStartMs = epochMillis();
    const unsigned long SESSION_LIMIT_MS = 40UL * 60UL * 1000UL; // 40 minutes

    while (!stateStop)
    { // block loop
        uint64_t blockStartTime = epochMillis();
        st.blockNum++;
        st.trialCounter = 0;
        st.rewardCounter = 0;
        updateRewProbGeneric(st, unstrProb);
        reportProbGeneric(st);
        int n = 0; // port index (1 or 2)
        int rewardPercent = 0;

        while (!stateStop)
        { // trials loop
            if ((epochMillis() - st.sessionStartMs) >= SESSION_LIMIT_MS)
            {
                stateStop = 1;
            }
            HouseKeeping();
            if (checkSMStateStopGeneric(st))
                return;

            if (Nosepoke1DI.isOn() || Nosepoke2DI.isOn())
            {
                uint64_t trialStartTime = epochMillis();
                unsigned int whenNosepoke = (millis() - stateMachineStartTime);
                uint8_t recordNosepoke[2] = {Nosepoke1DI.diRead(), Nosepoke2DI.diRead()};
                int whichnosepoke[2] = {1, 2};
                for (int i = 0; i <= 1; ++i)
                {
                    if (recordNosepoke[i] == 1)
                        n = whichnosepoke[i];
                }
                WhichNosepoke(whenNosepoke);
                rewardPercent = st.probArray[n - 1];
                ReportData(88, rewardPercent, (millis() - stateMachineStartTime));
                bool rewardFlag = false;

                SpeakerPwdAO.on(50);
                delayHK(500);
                SpeakerPwdAO.off(0);

                unsigned long lickWindowStart = millis();
                bool lickDetected = false;
                while ((millis() - lickWindowStart) <= 5000)
                {
                    HouseKeeping();
                    if (stateStop || checkSMStateStopGeneric(st))
                    {
                        lickDetected = false;
                        break;
                    }
                    if (LickDI.isOn())
                    {
                        lickDetected = true;
                        LickDI.clear();
                        st.trialCounter++; // lick trial
                        unsigned int randomNumber = random(100);
                        if (randomNumber < rewardPercent)
                        {
                            GiveReward(1);
                            rewardFlag = true;
                            st.rewardCounter++;
                        }
                        else
                        {
                            ReportData(-51, 0, (millis() - stateMachineStartTime));
                        }
                        break;
                    }
                }

                if (!lickDetected)
                {
                    ReportData(-52, 0, (millis() - stateMachineStartTime));
                }
                if (!rewardFlag)
                {
                    ReportData(86, 1, (millis() - stateMachineStartTime));
                }

                uint64_t trialEndTime = epochMillis();
                if (lickDetected)
                {
                    ReportTrialSummary(200,
                                       st.probArray[0],
                                       st.probArray[1],
                                       rewardFlag ? 1 : 0,
                                       st.trialCounter,
                                       st.blockNum,
                                       st.unstructuredProb,
                                       (unsigned long)st.sessionStartMs,
                                       (unsigned long)blockStartTime,
                                       (unsigned long)trialStartTime,
                                       (unsigned long)trialEndTime);
                }
                else
                {
                    ReportTrialSummary(201,
                                       st.probArray[0],
                                       st.probArray[1],
                                       -1,
                                       st.trialCounter,
                                       st.blockNum,
                                       st.unstructuredProb,
                                       (unsigned long)st.sessionStartMs,
                                       (unsigned long)blockStartTime,
                                       (unsigned long)trialStartTime,
                                       (unsigned long)trialEndTime);
                }

                if (changeBlockGeneric(st))
                {
                    break; // start new block
                }
            }
        } // end trials loop
        if (stateStop)
            break;
    } // end blocks loop
    checkSMStateStopGeneric(st);
}

#endif
