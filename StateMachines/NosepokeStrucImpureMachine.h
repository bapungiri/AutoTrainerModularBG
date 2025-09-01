#ifndef _NosepokeStrucImpureMachine_h
#define _NosepokeStrucImpureMachine_h
#include <stdio.h>

// State machine variable
struct NosepokeStrucImpureStruct{
	int rewardCounter; // rewards delivered in current block
	int probArray[2];  // reward probabilities for ports 1 & 2
	int blockNum;      // current block number (starts at 0, increments each change)
	int trialCounter;  // trial index within block (increments per attempt)
} NosepokeStrucImpureVar = {0, {0,0}, 0, 0};

void updateRewProb(){
	float ports[] = {1.0, 2.0};
	int sizer = 2;

	//permutePorts(ports, sizer);

    int unstrprob = 20; // probability to pick unstructured pair
    int strprob = 80; // probability to pick structured pair

	int unsigned randomEnvDraw = random(100);

	int prob1 = DrawAProb(); 
	int prob2;

	// NOTE: "Unstructured" block means the two port probabilities are sampled independently
	// (subject only to the constraint prob2 != prob1 and prob1+prob2 != 100 inside DrawIndependentPair).
	// "Structured" block means the second port is the complement (prob2 = 100 - prob1).
	// This mapping (unstructured -> DrawIndependentPair, structured -> DrawDependentPair)
	// is intentional; do not invert unless experimental design changes.
	if (randomEnvDraw < (unsigned)unstrprob){
		prob2 = DrawIndependentPair(prob1); 
	}
	else{
		prob2 = DrawDependentPair(prob1); 
	}

    NosepokeStrucImpureVar.probArray[0] = prob1;
	NosepokeStrucImpureVar.probArray[1] = prob2;
}

void reportProb(){
	float ports[] = {1.0, 2.0};
	for (int i =0; i<2; ++i){
		ReportData(83, (int)ports[i], NosepokeStrucImpureVar.probArray[i]);
	}
}

int checkSMStateStop(){
	if (stateStop){
		// End SM
		ReportData(111, NosepokeStrucImpureVar.trialCounter, (millis()-stateMachineStartTime));
		ReportData(121, NosepokeStrucImpureVar.blockNum, (millis()-stateMachineStartTime));
		ReportData(63, NosepokeStrucImpureVar.rewardCounter, (millis()-stateMachineStartTime));
		EndCurrentStateMachine();
		RunStartANDEndStateMachine(&endStateMachine);
		EndCurrentTrainingProtocol();
		return 1; // return to loop()
	}
	else {
		return 0;
	}
}

int changeBlock(){
	// Initialize variables for changing block
	int min_length = 100;
	int switchProb = 2;
	int unsigned randomDraw = random(100);

	// if performed more than trial limit
	if (NosepokeStrucImpureVar.trialCounter >= min_length){

		// check if random draw is less than p(switch)
		if (randomDraw < (unsigned) switchProb){
			ReportData(111, NosepokeStrucImpureVar.trialCounter, (millis()-stateMachineStartTime));
			ReportData(121, NosepokeStrucImpureVar.blockNum, (millis()-stateMachineStartTime));
			return 1;
		}

		// otherwise return 0
		else{
			return 0;
		}
	}
	// if less than trial limit return 0.
	else{
		return 0;
	}
}
void NosepokeStrucImpureMachine(){
	RunStartANDEndStateMachine(&startStateMachine); // Start protocol
	InitializeStateMachine();
	static uint64_t sessionStartTime = 0; // ms epoch for session start
	if (sessionStartTime == 0) sessionStartTime = epochMillis();
	const unsigned long SESSION_LIMIT_MS = 40UL*60UL*1000UL; // 40 minutes

	while (!stateStop){ // block loop
		uint64_t blockStartTime = epochMillis();
		NosepokeStrucImpureVar.blockNum++;
		NosepokeStrucImpureVar.trialCounter = 0;
		NosepokeStrucImpureVar.rewardCounter = 0;
		updateRewProb();
		reportProb();
		int n = 0; // port index (1 or 2)
		int rewardPercent = 0;

		while (!stateStop){ // trials within block
			if ((epochMillis() - sessionStartTime) >= SESSION_LIMIT_MS){ stateStop = 1; }
			HouseKeeping();
			if (checkSMStateStop()) return;

			// UNStructured Reward Probablities SM
			// detect which nosepoke triggered
			int unsigned whenNosepoke;
			if (Nosepoke1DI.isOn() || Nosepoke2DI.isOn()){
				uint64_t trialStartTime = epochMillis();
				whenNosepoke = (millis() - stateMachineStartTime);
				uint8_t recordNosepoke[2] = {Nosepoke1DI.diRead(), Nosepoke2DI.diRead()};
				int whichnosepoke[2] = {1,2};
				for (int i = 0; i<=1; ++i){
					if ((recordNosepoke[i] ==1)){
						n = whichnosepoke[i];
					}
				}
				WhichNosepoke(whenNosepoke);
				whenNosepoke = 0;
				// assign reward probability
				rewardPercent = NosepokeStrucImpureVar.probArray[n-1];
				ReportData(88, rewardPercent,(millis() - stateMachineStartTime));

				// if licked, give reward acc to reward prob
				bool rewardFlag = false;

				// delay for tone,
				SpeakerPwdAO.on(50);							
				delayHK(500);									
				SpeakerPwdAO.off(0);

				unsigned long delayStart = millis();
				bool lickDetected = false;
				while ((millis()-delayStart)<=5000){

					// If lick detected,
					if (LickDI.isOn()){
						lickDetected = true;
						LickDI.clear();
						// Count the attempt immediately
						NosepokeStrucImpureVar.trialCounter++;


						int unsigned randomNumber = random(100);

						// chance that Lick is rewarded and cycle continues
						if (randomNumber < rewardPercent){

							// give reward and report R trial
							GiveReward(1);
							rewardFlag = true;

							// Increase reward counter
							NosepokeStrucImpureVar.rewardCounter++;
						}
						else{

							// Report Unrewarded trial
							ReportData(-51, 0, (millis()-stateMachineStartTime));
						}
						// break out of 5s while loop.
						break;
					}

			}

			// After the loop, check if a lick ever happened
			if (lickDetected == false){
				// This is a true "missed trial" because the 5s ended with no lick.
				ReportData(-52, 0, (millis()-stateMachineStartTime));
			}

			// Report miss trials. 
			if (rewardFlag == false){
				ReportData(86, 1, (millis()-stateMachineStartTime));	
			}

				uint64_t trialEndTime = epochMillis();
				if (lickDetected){
					ReportTrialSummary(200,
						NosepokeStrucImpureVar.probArray[0],
						NosepokeStrucImpureVar.probArray[1],
						rewardFlag ? 1 : 0,
						NosepokeStrucImpureVar.trialCounter,
						NosepokeStrucImpureVar.blockNum, // blockId
						(unsigned long)sessionStartTime,
						(unsigned long)blockStartTime,
						(unsigned long)trialStartTime,
						(unsigned long)trialEndTime);
				} else {
					ReportTrialSummary(201,
						NosepokeStrucImpureVar.probArray[0],
						NosepokeStrucImpureVar.probArray[1],
						0,
						NosepokeStrucImpureVar.trialCounter,
						NosepokeStrucImpureVar.blockNum,
						(unsigned long)sessionStartTime,
						(unsigned long)blockStartTime,
						(unsigned long)trialStartTime,
						(unsigned long)trialEndTime);
				}


			// change block number if required
			if (changeBlock()){
				break; // exit trial loop to start new block
			}
		} // if nosepoked
		} // end trials loop
		if (stateStop) break; // session end
	} // end blocks loop
	checkSMStateStop(); // final cleanup if stopped by duration
}

#endif	


