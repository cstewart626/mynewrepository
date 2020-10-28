
#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#-------------------------------------------------------------------------------
# Name:        SW_Radar_Test__Probabilities_InISOC.py
# Purpose:     Generic radar test from given parameters
# Created:     1/12/2018
#  Latest:     03/22/2019
#-------------------------------------------------------------------------------
# ####
# ####
# ####
# ####
#-------------------------------------------------------------------------------

# ##############################################################################
# #################  imports  #############################################
# ##############################################################################
import sys
if '/home/summit/RDCode' not in sys.path: sys.path = ['/home/summit/RDCode'] + sys.path
if '/home/pi/RDCode' not in sys.path: sys.path = ['/home/pi/RDCode'] + sys.path

import math
import time
import threading

from pysummit import descriptors as desc
from pysummit import comport
from pysummit import decoders as dec
from pysummit.devices import TxAPI
from pysummit.devices import RxAPI
import rfmeter
from rfmeter.agilent import E4418B
from ds.Equipment.Vaunix import LDA602
from ds.Helpers import RadarGen
from ds.Helpers import helpers
from ds.Helpers import FCC_Radar, ETSI_Radar
from ds.Helpers import Test_Common as tstcom
from ds.Helpers import dict
from ds.Helpers import radarDetectorSettings as radar_settings

# ##############################################################################
# #################  classes  #############################################
# ##############################################################################
class SummitDeviceThread(threading.Thread):
    """A thread for transmitting packets

    Transmit a fixed number of packets. Set the dev_running event before
    starting the transmission and clear the dev_running event after the
    transmission is complete.
    """
    def __init__(self, dev, packet_count):
        super(SummitDeviceThread, self).__init__()
        self.daemon = True
        self.dev = dev
        self.packet_count = packet_count
        self.logger = logging.getLogger('SummitDeviceThread')

    def run(self):
        self.logger.info("Transmitting %d packets" % self.packet_count)

        if(pm_ready.is_set()):
            dev_running.set()
            (_status, null) = self.dev.transmit_packets(self.packet_count)
            if(_status != 0x01):
                print dev.decode_error_status(_status, 'transmit_packets')
            dev_running.clear()

# ##############################################################################
class PMThread(threading.Thread):
    """A power meter thread

    The power meter will take continuous measurements as long as the
    dev_running event is set.

    """
    def __init__(self, pm):
        super(PMThread, self).__init__()
        self.daemon = True
        self.pm = pm
        self.logger = logging.getLogger('PMThread')
        self.measurements = []

    def run(self):
        total_runs = 0
        self.logger.info("Taking power measurement...")
        pm_ready.set()
        while(not dev_running.is_set()):
            pass
        while(dev_running.is_set()):
            meas = self.pm.cmd("MEAS?", timeout=15)
            self.logger.info("%d: %s" % (total_runs, meas))
            self.measurements.append(meas)
            total_runs += 1

        self.pm.cmd("INIT:CONT ON")
        pm_ready.clear()


# ##############################################################################
# #################  Constants  ###########################################
# ##############################################################################
# # # Don't change these threading associated values.
dev_running = threading.Event()
pm_ready = threading.Event()

    # These channels are the <parking channels> during operations that
    # need the radios set out of band.  One for working, and one for monitor.
benignW = 0; benignM = 2 # Summit channel indexed of 0-34

_radsiggenlocation  = dict.port_dict.get('radar_gen', '/dev/ttyUSB1')
_powermeterlocation = dict.port_dict.get('pwr_meter', '/dev/ttyUSB0')

# ##############################################################################
# #################  Settings  ############################################
# ##############################################################################
#

# DFS Control
    # Bit 0 = Override On/Off
    # Bit 1 = Print Radar Type On/Off
    # Bit 2 = TPM Override On/Off
DFS_control = 3

# MRDC Control
    # With MRDC = True, We can look for the MRDC code as it indicates a radar detector fired, so
    # radar_on_M will become true even though the SYSLOG does not show a radar event yet.
    # However if in this case we _must_ look for a radar event, set MRDC = False
MRDC = True

# ##############################################################################
# #################  Defined functions  ###################################
# ##############################################################################

# ##############################################################################
def add2file(str_to_file, file_target):
    """
    Print str_to_file to the target file and flush the buffer
    """
    file_target.write("%s\n" % str_to_file)
    file_target.flush()
    
def create_step_attenuator():
    # Instantiate a Step Attenuator
    model='LDA-602'; serial=6318 #serial=5971
    attenuator = LDA602.Attenuator(model, serial)
    print ("Attenuator: .... On-line")
    
    # Use Examples:
    # current_attn = attenuator.attenuation() #Query the current setting
    # attenuator.attenuate(00.0) #Set the attenuation - 0.5dB Steps
    # print ("LDA602 Attenuation is: %.1fdB" % attenuator.attenuation())
    return attenuator

def create_radar_gen(show_radar_params):
    # Instantiate a Radar Signal Generator
    #    RSG = RadarGen.RadarDev('/dev/ttyUSB1')
    #print (_radsiggenlocation)
    RSG = RadarGen.RadarDev(_radsiggenlocation)
    RSG_is_there = RSG.radargen_present(False)
    if RSG_is_there == False:
        print ("RSG There? %s" % (RSG_is_there()) )
        tstcom.help_the_user()
        return # Bump out to RA upon problem
    print ("Radar Generator: On-line")
    RSG.set_debug_messages(0)
    RSG.set_show_radar_parameters(show_radar_params)
    return RSG

def create_power_meter():
    # Instantiate a Power Meter
#   Give it an open COM port and initialize
    #    COM = rfmeter.comport.ComPort('/dev/ttyUSB0', timeout=15)
    COM = rfmeter.comport.ComPort(_powermeterlocation, timeout=15)
    COM.connect()
    PM = E4418B(COM)
    print ("Power Meter: ... On-line")
## "=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-="
    PM.meter_reset()
    PM.clear_errors()
    PM.cmd("SYST:PRES")
    PM.cmd("SYST:REM")
    initial_test_chan = 19 #Channel to establish
    channel_freq = helpers.summit_ch_2_RFfreq_GHz(initial_test_chan)
    PM.cmd("FREQ " + str(channel_freq) + "GHZ")
    PM.cmd("CORR:DCYC:STAT OFF")
    PM.cmd("CORR:GAIN2:STAT OFF")
    return PM

def main(TX, RX, test_profile, power_controller, args, radar_params, audio_mode):
    """
    """
    test_status = [0]

    print ("\n \n \n \n \n \n \n")
    print ("= RA SCRIPT RA SCRIPT RA SCRIPT RA SCRIPT RA SCRIPT RA SCRIPT =")
    print ("\n\n") # This goes to the screen
    print ("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=")
    print ("-=-=-=-=-=-=-=-=  AUTOMATED RADAR TESTING  =-=-=-=-=-=-=-=-=-=-")
    print ("-=-=-=-=-=-=-=-=  Probabilities -- " + audio_mode + "  =-=-=-=-=-=-=-=-=-=-")
    print ("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n")
    
    country           = radar_params[0]
    radar_sequence    = radar_params[1]
    target_pwr        = radar_params[2]
    ampl_Nsteps       = 0 #Not used
    ampl_step_size    = 1 #Not used
    Ntrials           = radar_params[5]
    Wchannels_to_test = radar_params[6]
    audio_clk_rate    = radar_params[7] # String ('44.1', '48', '96')
    show_radar_params = radar_params[8]

    # --------------------------------------------------------------------------
    # Derived values
    (radar_region, MFG_code, radar_mode) = tstcom.derive_location_attribute(country) 
    
    # tx_bit_rate should use value in register... need to make sure this is set though
    # but if not in isoch then won't be set
    # rate in DFS file... may have to increase rate
    # may be changes in firmware that change data rate
    (tx_bit_rate, tx_vector_reg) = tstcom.Audio_Clk_Rate_2_TX_Rates(MFG_code, audio_clk_rate)
    
    if (audio_mode != "COMMAND"):
        Mchannels_to_test = tstcom.create_monitor_channel_tuple(Wchannels_to_test, MFG_code)
    
    RSG = create_radar_gen(show_radar_params)
    PM = create_power_meter()
    attenuator = create_step_attenuator()
    
    board_temp, my_MAC = \
    tstcom.init_sherwood(TX, desc, MFG_code, DFS_control)

# ##############################################################################
    tstcom.clearSYSLOG(TX, False) # Make the syslog buffer clear

    # Create a filled array using -1 as the not used indicator
    # It contains spots for:
    # Radartype  Channel  W_hits  M_hits  Trials  W_Probability  M_Probability
    results = [[(-1, _j, 0, 0, 0, 0, 0, 0) for _i in range(0, 9 +1)] for _j in range(0, 34 +1)]

    # Get the current time to indicate the start of test time in the filename.
    # Alternate format: file_time = time.strftime("%H%M%S%m%d%y")
    file_time = time.strftime("%y%m%d%H%M%S")
    run_start_time = time.strftime("%c")

    dfs_info =  tstcom.get_dfs_info(TX)
    
    # Get the temperature
    (_status, board_temp) = TX.temperature()

    # Set the filename for the human readable text file.
    radar_output_file4human = ("%s_Prob_%s_%s_%s_%sMb_%sdBm_%s.txt" %
    ( audio_mode, my_MAC.replace(':',''), str(file_time), str(radar_region), str(tx_bit_rate), str(target_pwr), str(dfs_info) ))

    radar_setting_file = ("radar_settings_%s_%s_%s_%s_%sMb_%sdBm_%s.csv" %
    ( audio_mode, my_MAC.replace(':',''), str(file_time), str(radar_region), str(tx_bit_rate), str(target_pwr), str(dfs_info) ))
    
    print ("Radar Region is %s using MFG Code: %d" % (radar_region, MFG_code) )
    print ("Target power level: .. %3.2fdBm" % target_pwr)
    print ("Number of trials: .... %d" % Ntrials)
    print ("On these channels: ... %s" % (Wchannels_to_test,) )
    print ("with radar types: .... %s" % (radar_sequence,) )
    print ("Data Rate: ........... %dMb/sec at %skHz" % (tx_bit_rate, audio_clk_rate) )
    print ("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n")

    print ("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=")
    print ("==== RADAR Test begins")
    print ("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n")
    
    outputinfo = True # Include the SYSLOG data in the output stream

    with open(radar_output_file4human, 'a') as f, open(radar_setting_file, 'w') as f1:
        
        # write monitor and working primary and secondary radio settings to radar 
        # output file 
        # just in case system args are needed later, store them off and then put 
        # them back after the radar settings have been written
        temp_args = sys.argv
        sys.argv = [sys.argv[0], '-ms','-ws','-mp','-wp',radar_output_file4human]
        radar_settings.main(TX, RX, test_profile, power_controller, sys.argv)
        sys.argv = temp_args
        
        # header for the radar settings file
        add2file("radio_type,channel,tpw,tpri,n_pulses,n_bursts,result,seed=%d" % args.seed, f1)
        
        # Main header for the report # This goes into the file
        add2file("======================================================================", f)
        add2file("RADAR PROBABILITY TEST RESULTS - " + audio_mode, f)
        add2file("DFS: %s" % (dfs_info), f)
        add2file("======================================================================", f)
        add2file("Device MAC: .......... %s" % (my_MAC), f)
        add2file("Region: .............. %s" % (radar_region), f)
        add2file("Radar Mode: .......... %s" % (radar_mode), f)
        add2file("Data Rate: ........... %sMb/sec at %skHz" % (tx_bit_rate, audio_clk_rate), f)
        add2file("Target Power Level: .. %sdBm" % (target_pwr), f)
        add2file("Board Temperature: ... %s" % str(board_temp), f)
        add2file("Run Started: ......... %s" % (run_start_time), f)
        add2file("======================================================================", f)
        
        for working_test_channel in Wchannels_to_test:
            
            if (audio_mode == "COMMAND"):
                monitor_test_channel = working_test_channel
            else:
                monitor_test_channel = Mchannels_to_test[Wchannels_to_test.index(working_test_channel)]
            
            amplitude_check_channel = working_test_channel

            # Post this sub-header for each test channel
            add2file("_________________________________________________________________", f)
            add2file("0_Type, 1_Channel, 2_W_hits, 3_M_hits, 4_Trials, 5_ProbW, 6_ProbM", f)
            add2file("=================================================================", f)
            
            if (audio_mode != "COMMAND"):
                # Take the system to a known non-ISOC state
                # The system should leave ISOC and have not lost slaves
                tstcom.leave_isoch(TX)

            # Move Working & Monitor radios to off-axis channels otherwise
            # the radio get bombarded with energy during set_amplitude.
            tstcom.set_sherwood_channel(TX, benignM, benignW)
            
            tstcom.set_amplitude(PM, RSG, attenuator, amplitude_check_channel, target_pwr)

            if (audio_mode != "COMMAND"):
                # Restore system to establish a network
                tstcom.into_isoch(TX, desc, DFS_control, audio_clk_rate, monitor_test_channel, working_test_channel)
            
            if (audio_mode == "InNET"):
                # Execute a network "STOP"
                tstcom.stop_network(TX)
            
            OBW = tstcom.determineOBW()
            
            Pass_Fail_Criteria = []
            # Get the pass/fail criteria for the test
            if   radar_mode == "FCC" :
                Pass_Fail_Criteria = FCC_Radar.Pass_Fail_Criteria

            elif radar_mode == "ETSI" :
                Pass_Fail_Criteria = ETSI_Radar.Pass_Fail_Criteria
        
            else:
                print("Pass/Fail criteria undefined... setting to always Pass")
                Pass_Fail_Criteria = {   0 : '0',
                         1 : '0',
                         2 : '0',
                         3 : '0',
                         4 : '0',
                         5 : '0',
                         6 : '0',
                         7 : '0',
                         8 : '0',
                         9 : '0'}
                
            loop_indice = 0
            pass_fail_str = "Pass"            
            
            for testrun in radar_sequence:

                (radar_type, profile, subprofile, trials2run, Signed_OBW) = tstcom.parse_testrun(testrun, Ntrials, OBW)

                Wmissed = 0; Wdetected = 0; Mmissed = 0; Mdetected = 0

                for trial in range(1, trials2run +1):

                    if RSG.error_state != 0: # Back to the RA shell
                        test_status.append(2)
                        print ("Status Code: %d" % test_status)
                        return test_status

                    print ("\n========================================================")
                    print ("Running Trial Number: %d of %d\nAmplitude Setting: %3.1fdBm" % (trial, trials2run, target_pwr) )
                    print ("========================================================\n")

                    if (audio_mode != "COMMAND"):
                        tstcom.check_4lost_slaves(TX)
                        
                    w_trial_pass_fail_str = "Pass"
                    m_trial_pass_fail_str = "Pass"
                    
                    radar_on_W = 255; iteration = 0
                    while (radar_on_W != 0) and (radar_on_W != 1):
                        iteration += 1

                        tstcom.clearSYSLOG(TX, False) # Make the syslog buffer clear
                        
                        if (audio_mode == "COMMAND"):
                            tstcom.set_sherwood_channel(TX, benignM+trial%2 , working_test_channel)# Force a SYSLOG EVENT
                        else:
                            tstcom.set_sherwood_channel(TX, monitor_test_channel, working_test_channel)

                        if iteration == 1: # Only shoot radar once
                            tstcom.ShootRadar(RSG, profile, radar_mode, working_test_channel, Signed_OBW)

                        if outputinfo == True:
                            print ("Scanning SYSLOG for Working radio events %s" % (time.strftime("%H:%M:%S")) )
                        (_mr, radar_on_W, _me, _we) = tstcom.checkSYSLOG(TX, False, outputinfo)

                        if radar_on_W > 1: # syslog status error
                            test_status.append("ch%sW-trial%s-type%s-%d" % ( str(working_test_channel), str(trial), str(radar_type), radar_on_W))

                        if iteration > 1: # 1=one retry, also to prevent infinite loop
                            print ("Working Radio Iteration Loop %d" % (iteration))
                            test_status.append(3)
                            break
                        
                        if (radar_on_W != 1):
                            m_trial_pass_fail_str = "Fail"
                            
                        temp_str = "working," + "ch" + str(RSG.channel) + "," + str(RSG.aTpw) \
                            + "," + str(RSG.aTpri0) + "," + str(RSG.aNPulses) + "," \
                            + str(RSG.NBursts) + "," + w_trial_pass_fail_str
                        add2file(temp_str, f1)
                        # End While Loop
        
                    radar_on_M = 255; iteration = 0
                    while (radar_on_M != 0) and (radar_on_M != 1):
                        iteration += 1

                        tstcom.clearSYSLOG(TX, False) # Make the syslog buffer clear

                        if (audio_mode == "COMMAND"):
                            tstcom.set_sherwood_channel(TX, monitor_test_channel, benignW)
                        else:
                            tstcom.set_sherwood_channel(TX, monitor_test_channel, working_test_channel)
 
                        if iteration == 1: # Only shoot radar once
                            tstcom.ShootRadar(RSG, profile, radar_mode, monitor_test_channel, Signed_OBW)

                        if outputinfo == True:
                            print ("Scanning SYSLOG for Monitor radio events %s" % (time.strftime("%H:%M:%S")) )
                        (radar_on_M, _wr, _me, _we) = tstcom.checkSYSLOG(TX, MRDC, outputinfo)

                        if radar_on_M > 1:# syslog status error
                            test_status.append("ch%sM-trial%s-type%s-%d" % ( str(monitor_test_channel), str(trial), str(radar_type), radar_on_M))

                        if iteration > 1: # 1=one retry, also to prevent infinite loop
                            print ("Monitor Radio Iteration Loop %d" % (iteration))
                            test_status.append(4)
                            break
                        
                        if (radar_on_M != 1):
                            m_trial_pass_fail_str = "Fail"
                            
                        temp_str = "monitor," + "ch" + str(RSG.channel) + "," + str(RSG.aTpw) \
                            + "," + str(RSG.aTpri0) + "," + str(RSG.aNPulses) + "," \
                            + str(RSG.NBursts) + "," + m_trial_pass_fail_str
                        add2file(temp_str, f1)
                        # End While Loop
                        
                    if _me == 1:
                        print ("\n   Energy was detected on Monitor channel\n\n")

                    if _we == 1:
                        print ("\n   Energy was detected on Working channel\n\n")

                    if radar_on_W == 1:
                        Wdetected += 1
                        print ("   Working Radio - Radar Signal Detected")
                    else:
                        Wmissed += 1
                        print ("   Working Radio - Missed Radar Signal")

                    if radar_on_M == 1:
                        Mdetected += 1
                        print ("   Monitor Radio - Radar Signal Detected")
                    else:
                        Mmissed += 1
                        print ("   Monitor Radio - Missed Radar Signal")
                        

                # Calculate the individual probabilities
                pWrk = (float(Wdetected) / trials2run) * 100.0
                pMon = (float(Mdetected) / trials2run) * 100.0

                # Overwrite the array at the specific location for this loop's entire
                # trial results. The remaining array sections remain untouched.

        # --------------- written to the results array -----------------
        #
                results[working_test_channel][loop_indice] = (radar_type,
                                                              working_test_channel,
                                                              monitor_test_channel,
                                                              Wdetected,
                                                              Mdetected,
                                                              trials2run,
                                                              pWrk,
                                                              pMon)
                
                # if a test has failed the pass/fail criteria, change the string
                # to show that we have failed
                if (pWrk < int(Pass_Fail_Criteria.get(int(radar_type[0]))) or
                    pMon < int(Pass_Fail_Criteria.get(int(radar_type[0])))):
                    pass_fail_str = "Fail"
                    
        # ---------- written to the human readable text file ------------
        # Output the results for this loop to the results file.
                out_str = "%3s    %3d :%3d   %3d       %3d       %3d        %6.2f   %6.2f" % ( results[working_test_channel][loop_indice] )
                add2file(out_str, f) # into the human's text file
                
        # ------------------ printed to the screen --------------------
                print (" ")
                print ("_________________________________________________________________")
                print ("0_Type, 1_Channel, 2_W_hits, 3_M_hits, 4_Trials, 5_ProbW, 6_ProbM")
                print ("=================================================================")
                print (out_str)
                
                loop_indice += 1
                # End of trials loop
                
            # add to the radar output file whether we have passed or failed the run    
            pass_fail_str = "%64s" % pass_fail_str
            add2file(pass_fail_str, f)
            # End of testrun loop
            

        
         # Get the temperature
        (_status, board_temp) = TX.temperature()
        run_stop_time = time.strftime("%c")

        add2file("======================================================================", f)
        add2file("Board Temperature: %s" % str(board_temp), f)
        add2file("Run Ended: %s" % (run_stop_time), f)
        add2file("Status Code: %s" % (test_status, ), f)

        # Prints the amended array section so as to not include the clutter of the
        # untouched array sections.  This shows the final results in human
        # readable form.
        #
        # ------------------ printed to the screen when done --------------------
        print ("\n \n \n \n \n \n \n")
        print ("===============================================================")
        print ("====   RADAR PROBABILITY TEST RESULTS - " + audio_mode + " =============")
        print ("===============================================================")
        print ("      DFS: %s" % (dfs_info) )
        print ("      MAC Address: %s" % (my_MAC) )
        print ("===============================================================\n")
        print ("Radar Region is %s using MFG Code: %d" % (radar_region, MFG_code) )
        print ("Target power level: .. %3.2fdBm" % target_pwr)
        print ("Number of trials: .... %d" % Ntrials)
        print ("On these channels: ... %s" % (Wchannels_to_test,) )
        print ("with radar types: .... %s" % (radar_sequence,) )
        print ("Data Rate: ........... %dMb/sec" % tx_bit_rate)
        print ("Board Temperature: ... %s" % str(board_temp) )
        print ("Test Started: ........ %s" % (run_start_time))
        print ("Test Ended: .......... %s" % (run_stop_time))
        print ("Status Code: ......... %s" % (test_status,) )
        print ("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n")
        
        for _i in Wchannels_to_test:
            print ("_________________________________________________________________")
            print ("0_Type, 1_Channel, 2_W_hits, 3_M_hits, 4_Trials, 5_ProbW, 6_ProbM")
            print ("=================================================================")
            for _j in range(0, (len(radar_sequence))):
                print ("%3s    %3d :%3d   %3d       %3d       %3d        %6.2f   %6.2f" % results[_i][_j])
        # ------------------ printed to the screen --------------------
    f.close()
    f1.close()
    
    # ##############################################################################
    print ("_________________________________________________________________\n")
    print ("====  CLEANING UP  ==============================================\n")

    if (audio_mode == "ISOCH"):
        # Check TX Vector Rate
        tstcom.check_TXVectorRate(TX, MFG_code, audio_clk_rate)

    # Re-enable power compensation
    (_status, null) = TX.set_power_comp_enable(1)

    # Take the system to a known non-ISOC state
    tstcom.leave_isoch(TX)
    
    # Unlock user control of power meter
    # Put power meter display into non-hold mode
    PM.meter_reset()
    PM.clear_errors()
    PM.cmd("INIT:CONT ON")
    PM.cmd("TRIG:SOUR IMM")
    PM.cmd("SYST:LOC")

    RSG.radargen_closeport()

    attenuator.close()

    print ("= DONE DONE DONE DONE DONE DONE DONE DONE DONE DONE DONE DONE =")
    print ("Status Code: %s" % (test_status,) )
    return test_status #Back to RA with status code list

# ##############################################################################
# #########################################################################
# ##############################################################################
if __name__ == '__main__':
    pass

# Start the test
    main()
                        