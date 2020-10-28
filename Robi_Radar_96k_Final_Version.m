% This program reads and plots Radar Pass/Fail Histograms
%

clear all;
close all;

Path = 'C:/Users/cstewart/Documents/Robi Radar Excel Sheets/Robi Radar Setting 96k.csv' ;
filename = 'Robi Radar Setting 96k.csv';
data = readtable(Path);

radio = {'working','monitor'};

Moniter_Data = data(2:2:end,:);
Working_Data = data(1:2:end,:);

Working_Data.Properties.VariableNames = {'radio_type2' 'channel2' 'tpw2' 'tpri2' 'n_pulses2' 'n_bursts2' 'result2' 'seed'};
Total_Data = [Moniter_Data Working_Data];

Type_0 = array2table(zeros(0,16)); Type_1 = Type_0 ; Type_2 = Type_0 ; Type_3 = Type_0 ; Type_4 = Type_0 ; Type_5 = Type_0 ; Type_6 = Type_0 ;

Type_0.Properties.VariableNames = {'radio_type' 'channel' 'tpw' 'tpri' 'n_pulses' 'n_bursts' 'result' 'seed_532597141' 'radio_type2' 'channel2' 'tpw2' 'tpri2' 'n_pulses2' 'n_bursts2' 'result2' 'seed'};
Type_1.Properties.VariableNames = Type_0.Properties.VariableNames;
Type_2.Properties.VariableNames = Type_0.Properties.VariableNames;
Type_3.Properties.VariableNames = Type_0.Properties.VariableNames;
Type_4.Properties.VariableNames = Type_0.Properties.VariableNames;
Type_5.Properties.VariableNames = Type_0.Properties.VariableNames;
Type_6.Properties.VariableNames = Type_0.Properties.VariableNames;

T_0 = [1 271 541 811 1081 1351 1621 1891;30 300 570 840 1110 1380 1650 1920;
       31 301 571 841 1111 1381 1651 1921; 60 330 600 870 1140 1410 1680 1950;
       61 331 601 871 1141 1411 1681 1951; 90 360 630 900 1170 1440 1710 1980;
       91 361 631 901 1171 1441 1711 1981; 120 390 660 930 1200 1470 1740 2010; 
       121 391 661 931 1201 1471 1741 2011; 150 420 690 960 1230 1500 1770 2040;
       151 421 691 961 1231 1501 1771 2041; 240 510 780 1050 1320 1590 1860 2130;
       241 511 781 1051 1321 1591 1861 2131; 270 540 810 1080 1350 1620 1890 2160];

for i= 1:size(T_0,2)
    Type_0 = [Total_Data(T_0(1,i):T_0(2,i),:); Type_0];
    Type_1 = [Total_Data(T_0(3,i):T_0(4,i),:); Type_1];
    Type_2 = [Total_Data(T_0(5,i):T_0(6,i),:); Type_2];
    Type_3 = [Total_Data(T_0(7,i):T_0(8,i),:); Type_3];
    Type_4 = [Total_Data(T_0(9,i):T_0(10,i),:); Type_4];
    Type_5 = [Total_Data(T_0(11,i):T_0(12,i),:); Type_5];
    Type_6 = [Total_Data(T_0(13,i):T_0(14,i),:); Type_6];
end

PassData = data(strcmp(Type_0.result,'Pass')& strcmp(Type_0.radio_type,'monitor'),:);
FailData = data(strcmp(Type_0.result,'Fail')& strcmp(Type_0.radio_type,'monitor'),:);

figure
[PWcount, PWcenter] = hist(Total_Data.tpw);
[PRIcount, PRIcenter] = hist(Total_Data.tpri);
PWfail = hist(FailData.tpw, PWcenter);
PWpass = hist(PassData.tpw, PWcenter);
PRIfail = hist(FailData.tpri, PRIcenter);
PRIpass = hist(PassData.tpri, PRIcenter);
TotalData = height(PassData) + height(FailData);
Pass_Prob = round(1000*height(PassData)/(TotalData)/10);
   
bar(PWcenter,[PWpass', PWfail'],'stacked');
legend('Pass','Fail','location','southoutside','orientation','horizontal')
xlabel('Pulse Width in uSec')
ylabel('Occurance')
title({'Pulse Width Histogram',[filename,': Type 0 ', ' : Radar Probability = ', num2str(Pass_Prob), '%']})
txt = cell(1, length(PWcenter));
for k = 1:length(PWcenter)
    txt{k} = ['\bf',num2str(round(1000*PWpass(k)/(PWpass(k)+PWfail(k))/10)),'%'];
end 
text(PWcenter,PWpass,txt,'HorizontalAlignment','center', 'VerticalAlignment','baseline')    


figure   
bar(PRIcenter,[PRIpass', PRIfail'],'stacked');
legend('Pass','Fail','location','southoutside','orientation','horizontal')
xlabel('Pulse Repetition in uSec')
ylabel('Occurance')
title({'Pulse Repetion Rate Histogram',[filename,': Type 0 ', ' : Radar Probability = ', num2str(Pass_Prob), '%']})

txt = cell(1, length(PRIcenter));
for w = 1:length(PRIcenter)
    txt{w} = ['\bf',num2str(round(1000*PRIpass(w)/(PRIpass(w)+PRIfail(w))/10)),'%'];
end
text(PRIcenter,PRIpass,txt,'HorizontalAlignment','center', 'VerticalAlignment','baseline')
