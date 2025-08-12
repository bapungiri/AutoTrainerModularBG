#ifndef _NosepokeUnstrucImpureMachine_h
#define _NosepokeUnstrucImpureMachine_h
#include <stdio.h>

// State machine variable
struct NosepokeUnstrucImpureStruct{
	int rewardCounter; // Number of rewards in this sm
	int probArray[2]; // reward probability array
	int sessionNum; // which session number is this 
	int trialCounter; // which trial are you on?
} NosepokeUnstrucImpureVar = {0, {0,0}, 1, 0};

void updateRewProb(){
	float ports[] = {1.0, 2.0};
	int sizer = 2;

	permutePorts(ports, sizer);

    int unstrprob = 80; // probability to pick unstructured pair
    int strprob = 20; // probability to pick structured pair

	int unsigned randomEnvDraw = random(100);

	int prob1 = DrawAProb(); 
	int prob2;

	if (randomEnvDraw < (unsigned)unstrprob){
		prob2 = DrawIndependentPair(prob1);

	}
	else{
		prob2 = DrawDependentPair(prob1);
	}

    NosepokeUnstrucImpureVar.probArray[0] = prob1;
	NosepokeUnstrucImpureVar.probArray[1] = prob2;
}

void reportProb(){
	float ports[] = {1.0, 2.0};
	for (int i =0; i<2; ++i){
		ReportData(83, (int)ports[i], NosepokeUnstrucImpureVar.probArray[i]);
	}
}

int checkSMStateStop(){
	if (stateStop){
		// End SM
		ReportData(111, NosepokeUnstrucImpureVar.trialCounter, (millis()-stateMachineStartTime));
		ReportData(121, NosepokeUnstrucImpureVar.sessionNum, (millis()-stateMachineStartTime));
		ReportData(63, NosepokeUnstrucImpureVar.rewardCounter, (millis()-stateMachineStartTime));
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
	if (NosepokeUnstrucImpureVar.trialCounter >= min_length){

		// check if random draw is less than p(switch)
		if (randomDraw < (unsigned) switchProb){
			ReportData(111, NosepokeUnstrucImpureVar.trialCounter, (millis()-stateMachineStartTime));
			ReportData(121, NosepokeUnstrucImpureVar.sessionNum, (millis()-stateMachineStartTime));
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

void NosepokeUnstrucImpureMachine(){
	
	RunStartANDEndStateMachine(&startStateMachine); // Start Training protocol

	// Initialize SM
	InitializeStateMachine(); 		

	// Increase session counter
	NosepokeUnstrucImpureVar.sessionNum++;				

	// Initialize timers/delays
	int delayStart = 0;

	// Initialize counter
	NosepokeUnstrucImpureVar.rewardCounter = 0;

	// Set probabilities for this block/session
	updateRewProb();
	reportProb();
	int n=0;
	int rewardPercent;

	// Initialize variables
	bool restartBlock = false;

	// Loop until stateStop = 1
	while (1){
		HouseKeeping();

		// check if stateStop is 1 at every moment, and report end of session
		if (checkSMStateStop()) break; 


		// UNStructured Reward Probablities SM
		// detect which nosepoke triggered
		int unsigned whenNosepoke;
		if (Nosepoke1DI.isOn() || Nosepoke2DI.isOn()){
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
			rewardPercent = NosepokeUnstrucImpureVar.probArray[n-1];
			ReportData(88, rewardPercent,(millis() - stateMachineStartTime));

			// if licked, give reward acc to reward prob
			bool rewardFlag = false;

			// delay for tone,
			SpeakerPwdAO.on(50);							
			delayHK(500);									
			SpeakerPwdAO.off(0);

			// 5 sec timer for lick detection
			delayStart = millis();
			bool lickDetected = false;
			while ((millis()-delayStart)<=5000){

				// If lick detected,
				if (LickDI.isOn()){
					lickDetected = true;
					LickDI.clear();

					// Increase trial counter,
					NosepokeUnstrucImpureVar.trialCounter++;
					int unsigned randomNumber = random(100);

					// chance that Lick is rewarded and cycle continues
					if (randomNumber < rewardPercent){

						// give reward and report R trial
						GiveReward(1);
						rewardFlag = true;

						// Increase reward counter
						NosepokeUnstrucImpureVar.rewardCounter++;
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

			// Report no reward/ miss trials. 
			if (rewardFlag == false){
				ReportData(86, 1, (millis()-stateMachineStartTime));	
			}

			// change block number if required
			if (changeBlock()){
				restartBlock = true;
				// break out of while (1) loop
				break;
			}
		} // if nosepoked
	} // while (1) loop

	if (restartBlock == true){ // restart the session.
		restartBlock = false;
		NosepokeUnstrucImpureMachine();
	}
}	

#endif	

