"""THUNDER THUNDER episode 91364946 player 0: distilled trajectory with the tested c17/c27 controller."""
import base64
import copy
import json
import zlib

_TRACE = json.loads(zlib.decompress(base64.b85decode(
    'c-rk<%Whm(lKdC0YoV&5WNCJ^RNWGqHU*OELXSZh2BsSW40;xx*$w*NM-SHPW@Kb!=DB>>Ub#$F-Fx0AGcq#rr~f<q$1lJB^Y6c&{o7AxA1`ih&h8dx|M|;*|HuD){=?^w|NQ0G|N8s?e*XN^+4~RIo6rABKYah`Z$DrB_~D0(%d^GV+pF!_Vrl+-^M14Wc(yp-{lm>>^X~JXx9>L>w`Yr&lRy8kxxD)E=+7UouikxndwcwYyMHZCdhy}yUp{?2djGyZKb>tiH@9CKy8m$B=cAwP+jrc3?;ZDzIDN~HSJ$`izdrQv$-d|Qr}RDd%~YTL{ihF??|%OLzqg;hObB`K<ePfyFE8G1_Jc%+=>D5uX5r-dpa0><+x^Ts@A=d5qF}E%{o=`7U)*l4z30EZ2nOie7x1|3da!%x(R1&=#KvW^$<X5tO)pHXeZk>zVA<;vYM;A*nm-`&MB2ySTz$G9a4;U>1p4EASa^0gD)V>LI)5Bm^S3{>>^OAhPZ^NL{7K_dnaAC4!Ek)*K<#md^)~%e?Rj>1hpYzH{nl#OJ!Eq+a1kh@F?bDp`;d4XvU9@gAY5s0uP!e)Z*PD8)8_j2!{vv6|JqD@pQLX8!nK8(K_0NX<x&j=Zw(t7j83xIyS+Pdf-0N8eqj9ZlRtj)gnn{*Cf;l=zqoEkJLQ{4hCM*zqrJLI`A>T*BtCh3^WXYei`r3U{GrpKfgN7nCC{2kKRUO=;Zm$L6rBIC?Me&%y9Bo}{<#^Z@Q~lx2ZM(R3_c#EN&~0%ergdMc};~^+W{^#;V{6a1@icUX>$fRY#{S23rDFLqQW!wBV>Q8ju3b#9-#7V@q77g^{P9$^G;FB<>b#dx7Qcj?>E=ie>+>Oi<jZ#!|+RS)b;o{7iIU#+_|SmGu7>h<cci-P+7iG^?SoM&K_%cMA~lE^!jbx6Tt7I7x9P=7}zsALSPaR)*1VfiiLDo9;N3U8s_5PgUn3N^w5kDYcEVN!PaGK4-OZADmHQgx^=F;KOQpXAw9dG<?)g;aT+fD<L)2jF83Or^azV>HvV(bMROeKFRS<B`mcox3=Af@Cd!~g!o&d&1%b4RlRR~?rRLlp@Y-^Ij7iX4?tSZ|jvu~_J#ZWS&d2atwgYj`_qVb#A-YFy!=dslNujVxpMU#T_wMBW?yE6ebMqZ?lkWYW_vlJ>PicDnuQJ9#19Ct%LhORY?&*VA9FJ`xAP@5a>;=LO^9_gi*!CD<LlFUgC8~oRAHp6RAR1=157t&V+?V?+>D!0iCYnBW1gztrA`gIcCtPtB6BrvEc=zGY{flt^A+6vU>?xZOaE99Lhwj}I#T3?gOhK{L!E2tDZE)<5!~n_+I7G&s^kIl07ES*8OGF<S0>ogAQ3DSg&*At-hjW4qnYtCA2aq0M=(m+|XLd}&^stY?3n6^ayX&iu!8#!3)xnXxy1KkSslf@p-g$qYZ?AV}v1w<)2J~v;g|0@%pm$Hq92~ky%AL^tbM}i(e=>1d4v#gc*u=6((6T*W2IQI~7N~Mn+K^Gf6TqoGVg$SdzI@#?OS);446_tIvnqlhUw^#DD^Uxh$N`)+*`;rELS;AXvw#sQIl?mlzEMBT3iF`%s>FyPE!80+klp5+A9LB1!2EMY$LWSW@++%rdic{3SYWnA$50EF*Xd<}4wW4Frsii5uf>})ww?xajCZd>QzNgPp?p&Wo!VD=6V>ugz<Lhe2Uqk)wGRM`%B)$i1bpK;Ve%*>WPpA~a3gas>M$$`uxjTW8pZ*1DtjbOj6=LIY|vjL4{C{1&V4E{$|P5UAh`Cyli4BWNMh;2jM|f3gC4s#xOd3#;Y)=##(Y0y<D;*4V$fh;fVYd+NCk&wNbzE}xU`#mIxj|i9Kb#}G9%rl1$I?NhLpKOW$*}Mz;XeRV~1+xI#es&=9OHT!+mYXsFP9ayzcn?-Vdy9@vrU%Wap~xQ^t{0GRUwCWKF199H0<KUN9CAvao84g8MtBm5|Of^WqS^9%IxAtTl=9V9my<Su`kmaJcoHQOKm{DU4NM8oS<b?p?twI@Z?7l2%xA!2Sm&>)~x?>|NhEUOX&55!#UZ$zb`Ui5H?R9G<h`A_A_Re;QB^H<J@ePAZ@L=wcoF;ZW97^>hNG5BAm&qUQ95UIcvDj)}}fco-toFpqI?Zm<dND+-N$(F2<JKYY0S%NJ-LM@W`0tku74hfP`*{mL<TxJA$0fylTQ@N&sK$BdDTWh#&WBx`skUaLwSKy9=aTcu6wtl5Zws^}sdz-cLPLn5CqKCmkklF70qhj$(E%u`MTW1fx6D4&CxjE4nXST2pA23Q)Qe*l6SmE>2#`wk;vF=TJHjLQWH7j3JT`*#3KjjYE38-)!4@*$!nXy##1GCX&NgC%IlT1goj8*l)bb7CyEh0YT1@pyIi)E>=;<3}_1XB-h3F8dj{^5p#!Wt*8&!4`qq&3vz&JESnnix?y8l@m-jFc=5B7_$w+5CYj$cD(N(fiq8ckZh<HL{Qk5hVb+q$t&%RLF0V}c{eS<9z|Q%4k46-to7gHu8l(5ZJ(`M=jX9I*5bD3Gh3s{N(~>HoAUUk0^UJPOzd*cZ3M#7R9oL7&PT%B+PtvXU)}`;9T3oW+Z|wfIw?DVXjQ?QRnx$33D9~dLr-cL%!FG5>HfeJ3Qq=LAEVCF`I(GFMWPw@2@tQ5UG4j?4&y1~V@xKQ2uR}1LI^mAg>#>i0zD!p-)R%4sNCBxudrG3hHxZaxf}_FGznDR9cqq9%#xY0Z2E0<1(ZC98G|WCNeVK6kf#@4geZ&RPbXb^vi`x_LS#!u62Vcr-y}XZfx8rKh~v3@t*2Yeu<}W;aq>+tP|Oq%N2<A6qeGe7KrSug_}{)Q0zSKyBV53;eWr8JuK;1w(2S&{U~?gAHyW+3#I8qKv|uH`n|w{mJkkB}Lhy!cpXw`9v?K}<>U1{}0+!<znbM7L#xj?H&i|)WW`DUQSPBnEG#HU``H)bb2L6r2>qLq&#Oo+%qNRqOH)yE*TFN0hP4o>lC4;|ZTQ)ba7G-||P=TQZ=msnIi6Cq<uquWlPfFsK!n`P>dIE3Jop;@JJ*<Nh2mc8W_$j46Ru?Vj_^@?r=Qg)&(Ov`VswlY{(uAccUIZJprQ!;c(9FbfBcDifR9Me!cH?~{Vjb~zw+%b|dY7GNQwJyupWIuu5eo6H+-_i$nVz&ygbH|~E_j`_<bhDgRa)>ChnPo)ngP>^5Q|#?wU~IF&!-IO9uc=`3==y^2C*tS560SHF8t#*;&~24m@K<o0p9$JXXf%oG#4UGomYll3#5M#2t+E8+()**J)XFg`!7q~hkkvhC|nW}KKDE9Fu3fOQMm+3Uai2(dGG`Sg_`?VUO$>h5R%iZ0v<*m!#h^iZo)Hy7Tf-JryEg=B*7h5O<eX8@yecOS}zq25TyD_$}92s5wUTvc1D5+%-w)-nlM|!W1u5uzn;)b0Z~lCNz{i36EiZ!ZT)q(r4JU;f5@uH6qh6G4zss_8^s;;v8qF4S71_LR@byvtj2n$9Q-AsS{p)a$((sSkZL$tbT&_|5citsX^{~Z(3wQvAkr?5Rx^*sgt*N9d((S^L@JdSq@0UJX1K6505Xz`YKsKsQsK*r-@4$G#&8;~K6TNJ_8Y;X<A<>DNs7q%U8CC4%2WJ(W8Sk|J;zj&IjS%96YIB*o<};tz9)U8etP)$^3%xD(Bf?bdKeuf?grb`QXGv{mVyY9mJw6fsvz|+2L;kpXI*AYKb3W`vB*e7YanO1CxnDt7e))MAq-+xHV-CRSEOR0GS?=-dCi1aK`Xqzz*T9#(>SGhk~%tzYq8Z_<_}#Ugy~PY{{`7KbuCh>drS_!D0xCS3-jgETf4(LeuHbWvCOqv?$;0<vu76Ue9~{s#WAf^m`UL}b;Hh|kVhrw?9b;~0e8KTlJAEv#}xc=9}n!HAZ0LtoeM==wjfd@leZqL#*1w<V|Mj?uXVo!a4{i%8)sM7_?TROIr*=popGFv9>paW+2DR+kdzI=@;Vg*`ysT`?9Pb&G9n=n<YQ`WMkQiAq~8xZfKa2Z{+jXe5XWz$lN)C+=J}Rnawp@5f>#0Y_XBb?9<0<)jDWE?4x79>*Mn*QgnJfzlkA;_(5L8HVjoWdTfF9-n!M}ScunaCB2uv@gOqYL7!BIr93Vh8WI6@E6w!|5-C}c}nP*sUB#{=1;-1A+-_`*3GJNO48*;hDBL|5@DBm~{#n-<LQty1E-8i7QE+w`)B;9m=tH#Y8p~u$n%W2%v@x$kGd1bX`;EQGH!yvLZhnt?t4C4{fyz8WhI!m{8DHX9Xs>z*`DKG-9wAx}=-*tAGT^TsoOi8iWKuVdB@~-1DI1*Nn32Vsw$biqfA9`q(+dmfRw+i(!NWlllNd{qJf^;M_N%h6RdD%pNks^|+q$QNvELM%D++-|ZhZ@sg)pVd}B)vrY)XI(F0oZHS@On$|x;im{PeMTxn=9mSGc?L(no>KG`trHl;Y~OxDt^|f{*_X=aDy$a%y_CWv|mAl-t4(<BIVP>m`*5~uM-kU*6+3fmzElpUEC5eS75Hq70*2m(k{=PQGey-t4?O(83uHdBJ9Ub=>x=q$M9^SGrV^HB~*Ebzj`T@!7bPtkw>38{QMiPrXHS&M<-Zq0#5K0qSjiWE*^Acy{Xhdsz<jITA6yPtriL7Np-P*m@o*B`REZcAJ7M*IO5<cWF%%z+%;&|vTQsa<4H)sNaeDHpbB*kQ1B8vIE8i8P9TVqy=m14b{+@`b2SLSkqnkY^>|IX8;!9mDq=ZOMj_gv*<uulqppj^P*7M*dJc;x^lH8#?w*+dg;S7KI*7EcW9Bo{L2L02w7hwC5*HQ}z{c_5g6m4BC{T*lFoudyemUkTAhbz2j}$2;tr)J|Enu;TjQSj11PKBGE`55DF+DJ{{RQa`rUkiG%2&H#rC^pMiL+SQZ8v)|4>ByaQnC2OGT;Oh0z@!{&>~b|X_A9d8T5xLF46Iwl@O1>yVX)uGapmr{OL%SlRR@%q2<}uFMI&ltD|x*=Ryq1{mmBQ_8gpI3b3M36?iq<&EttX1H~hOUbyWA{g)+;azUquBy<#VMTZC<=$cY!DfMdJ0XDL0<x!Rt$uNGX1-hkN1nN^a$Uah7QdpQ0xjw-~V>|_R!iY?@u?5E?ji}fMq{v%ku$Y1GBY?b+eTiM75^pG3p&%onIEvt%;Z%`J19mV*NZ3*jG%6WCXQnYDc1B{E7l+E)p*-aWgY(t{IPxwBc<T{0mYkInG$g$NSz}~knQtJmp)2Ayti@CV&lh1=<oSwY$Wj+%J@yP0%r*u>3<{Bhe}5#+WA)mk?Y~hJ(T=DO&!6RSB2RwvezW<=1j<*BEl`dyGnczj5&VX9?GEK^yBWi=XzFlfq2=L>5NibFRL2QNwaEBb5Auybhh#PKTsWe_1S#gOMp&ts3|a~;W(xt}WCO*u=H-fp76)*Ij#;L1E`PowLy#{SkWUQ&CV5;Jeh%Um16IJqsoGmJ6%pXBLrUv087>?m5{Z|+;O+C%q*NG-QSPaNx5YDAJTlaE?W1&5h(0BxUgqai=tXS$1aWmCKco$1Ac#ei%t!ldME<-6yo9I*M*0FXwv#q4jWU!<5KaO_jPB>%i)GB=2mz35Gj41bjV>r6<g5lrs9ip&>9p#dQdh4JdkpG{;?%>Xpj5jr5D@@;(dZ2xq;ER$p6(%#NL(|m2+-I^fmnv-&v5F%Y5;Y>*CQ-t(9q-7%|mh0VsfGOIqIz|NKs0qVn#v(fMn9FU#Yo|sj*M%yk?azfaS)1F&jTZSLj1?wySMSArzkJ-=|T){9_?aMo$PLIswR|-i?Zq!d%pTl=5mEh*$BUm<mRH4qF0}oWa3rm2D*Oua<Bgx~yc7^U-i$7cfv(3h541Z82AK4~JQW#0Y#+D)YiiW7|fDryh~h<XGEo@0UtNrRrqma?WUmAIY)nk3P@}B4$G%4wTQ%tZ1HA?n!bYle3AI0N!S{00XeJ!P_XPvRI~1NF=Jt&`R^Kn>92qC?HzZ<|T-{7D;Zve3nK^x!*I>BY@>$<y#u!lcF!FNnm$rYFpE4D+=O1Xdi$h9-2=ybA**>w9r+BXBK&c;p(@{uAK7d=o&Lp^~ThPZxEZJ0aH(cIT4UKp&Y#c;MVe4r@=H8WX@mC3WyCZC&JOMmqo#tIU=n2`XkKQVIlKMxoS(<Oq5I4ZohotixG(mx<5|*z5{7gDHk5`VCXkzm6FjjFXJ%vrd97a8Y7}icR1QNmsdZ2(E!Wn4vMx|noXtIOha{MNK$vaMWMhVt+i2MD5U015~cwzwuRJ~FoELHIhJ#Q>~}s0m`BX0t_BqN(;?hxMi8tGV!7SV@lq(L%dWB*?+Xz_C@1WnRI!3wqMVI?IeV8R<l@G7#$-yODwE+>)N1tj5}PFECxQ{|C>q@(2aX_$ai9})IVyNXqXJY;aY@M+jwws~$<M7+&KggNj(bxbWejMmO)~YU@T{Cb8uVw{5>DXr&}E)j8^mpsI(@MR0#<C2jtaldtT57EYz)>HsF1$~#DJA6SCHci#Gkkuni0`wn$T$J6kuw(j)6t%w)sFO*Mbj-Ygv#z2S*n25m`0y{TXHXZL}YO#wMiDQHruX{4h>;ewXMSAtHtv^YEJ|Ul0_I5YHU+(;gG68pgRdwiitO{sc`0xaT)4^!KilUCpR`d$ql%+riT#Up&e}o5$IpLZRad0S?+uu<;zagQ}Ju;JfTF;zsZgqogoOVAE)B!^M<%O{x^Gy5PzYk!_RMOXJj-{0!B|m=o<lPbq15X)Hn>30ayEz^n;Mw<wtK#Gr-0^i0Mb(`ff!v8GO=Vx3Y4EF|*SQUCtahs$?Af4<pnKiyC5o>tl|5F;HMO8pv43VplTUpyJf*CB<i+tOHAi7KQ1<>VMqOhrC8m0Tgpo{IKV0BkX=!|cJ(pSm}vkJ@fmJumady}kV(EhC$`{myLgQa!*zIrY@PZi_D_ABD!99`8B;TnV3rt+C9aj%|g?hj_`OU_J$91TB22sCzHppIK)>6_N31S#7O`SQbcvrj-OsdWll-gO=t?Fm+z&scg{^Pc`vH!FsN+&$1f|q&vIt^m>s|(TtP1aL<s2PJ^mCk>hVl{RBW8JwQUUC|Fp5Vw%B-$Xy8px?*Zxp=S45GQA;yB~=3iZB6NebvcIawq^tT2)f$GXWjZ3u=H`bHLG9uY!SCPs;{rdXU%Hp%@D#LbxXaYoHOJ`WY_VSPZAg#BCAuN<<+qt)pXXpQUK=Yj;O3dM$?`f1Fx)N6n6}QUJ>Pf?1JX8Y|0hdX!@wb*D>UR5br6dpF?u+>bcX2+U%*M@R*l3IQLuO_(joZ{V1v9!lEX)4x&<biAe6shXlAwS=c^U#d?b}w;V|!7bMJyw>awoq2==%PFi&EvcixmzdUi{B}%iYS;>f{)k{6*{-?vxq^z+L;VFtW26-e=^?;u0w<Ij-@4+N}Gi;bDXfH~`)o%Y)%kL`g1M<Yslxq5gQX2}ZY<MF^*2{7!GpkpQ6Te*jPVxl<$Ns$N*uSh&W&EcRsY(`Z8X~Y-cc*=Cg|&VVYLGKT<QzxJli}m>2vxrnutD;8f;%VTR>o{0X5T>aEx92n)({4TPPrMC*-GpsN$;VW(^#25C5BtAekxHrBD#~BaFkueGt_5SiZ6@eEKId6(q!;LJ<<HF#vl|adz&!5ke|ZfuO$1wRQ|%|G0+%%B=zg3=-9PBboa@@PghAP2B;7bpN-LE$&cTkS>j|+s#2ivEwntgc9Aqg#zT9@k`O~B2c$idJ5v(){Z_f02>-8`zaOA}?rO-D1<)WaTD&7jc2k*+)zd^Kx-bMx2F)y&g~6}-(ZM9xXj#NW2CS+}YCqJ@2(sMJIUo}61L&JZ+q^?>_^Oj+5om`k-^rR@fWN_$Ju9FRIo2ZxE|p;qI%9imoTeh!Nw`o{q-*0-dZ_DS(<m$LXC*U3IFo3E;Rj9sE#@b_ZYYVp@e=CJJ#=sh6vkfvc4`&o2|&vtPPnE?WNSe+pVv3^GSE`jp(s}$YrqC4WWHq*E=kXNW(Eq?f{K=tK=RI!gwVI6cxnMp%@hJF(1JXPuc<J5uQp+1Ku`tXLdimjG~%wqG(uxF07Q#UcLGIbR8Emy$l%eF(|kgbf0(658aUz!4oe0J6Wzg5ReC9#qyQ6@rI#TEJXuz-3YQztGJ%SZSU({Ff~L{f<TULp8&xfp)phW9q*SKE7epHXVJmS$aWewdvW-&LaFXP94(RsEl;|3ldX5XIZFDShz`5W#tsPSP17#mFei2)XiW288*${g`D^cr&NwkUZ1RQkCuF^Ba;vKKa<tg=B7~JenVcMp)xw>pQ1-T4VWIz&@f*$oNcR6L8umJw0dAh!6Dp*DZ%wVM^dTE6(l+vw%`+)$PCIrbMFr3TBU?i=2WC=<XZ<-x)@SQWc-f4LL8xvWoVL+TKcHWXvT5Bpu40<0O_ZEp?T3ZK+3bo{q>J5CF6fOpxixjSI9W0gQUl8rAC%fg69;-ejvmn&CtdJcS*q@mk6VAS*3;-%p-Og**#EKK;iL{7jP9q_PMn{pLn3O2VK57EfEdH&g@I<@{rtjS;z**FnmkPj9ceKosRCffEy-U}7PzCeKFep7RB3^>>c^Jt+$rjX8sn~Ar2`0rlhMlBCjxgv1F+*AqjJ!t8SrH*pxHbuyQTa}wbsPXIfY;E|_!-lLprr~#5F!y!E-B(x4iy#%VE1{T)|NQZst)75cqd2*c3ncx`o%I-;P*`+aymQ%hrg4yO-H4K;d6*2+dW`@pFnYP1%TS?L}3lF^uGxzw8RoX&syqdI-+wb0JX{l3fkDEvU!p->|;4xU6|SXqilQF6v3teZTo7b%&Yvfi8X6M_6RNf8lA#J)qhwJG&FZo{Q1844;RQuNH+7l`--p16jXV_8x{U)iC#yG*td=<wfgk@8M7-3dX=ogo()gNaZY%%o?M{rO|l-LSyU@^#X{mf3Lx|~K{5)UH_H6*PLeT^4MX-XE6uXYsT<c2_FBx@Lq`m_{8H<BRInqb%tbOZa)np5P6{QjwwrXB0EPM}k~q5k0j7XL)~My7fD0Dj1GyMfhK|nC$Am28w10+58oG5M5;|W&T2>{TkrM;3mnzwpla!cn^{z6^k$&7xO4FOd4EZ~f<k6>`UycNZB0`ACqU1H@nl@6)$R!@V@URTTaQPi-6btkekQtaKr!W>ksEMfYjJ1%pR(rW292r_LL6jOa&~N=5E*(u)p?Hc)5oo08Xr>4Ws?+2s#t;}*GD?B1>eY(5AV8<AobG^9>KC1^eh5%2Qm02Lb7EDgWJC?547HLI3>6fVxBDRlLsIop#lcN4I3zY+H0G2lO^vk}C{ppX9Z9XLw-jk5cZ~}<B#kS~nxxTuR`FTaT_#16BT7f?Q~KUzsznmVD|suYVlXzFB05sV97TU6ifK5!`p7z$sn5oFPsIpB1qJ1?Ne7oN>X{)Cln#j)OkqPMFN7@%^N|eIL*=a1uNn|{hnS%ypJ0h4S+Cc^yPzp**>TXkS(Jm1y=^yN<osnaU*x+-^SVQz=6t4Pk+60bszoTMe5~9*Qa4nOpa3^4uIa%j*VJWTR{_P-y84_!HW^PWNr*gguNJ9zc(}Tdm_yzAhP6vQ7c@Y+1W1(+-eF$~ygy2YDH!O5V$wXvqEik^2uVk*=dBoN!QK%wkK`sQ?su5<&g{X2`B9<7`?UhKI8_fEV5D#L2#S-^nRdg}0r?s@I%*+cM#IZTmorEzGb9}kHpseo3g;dX?Zw>mBX^sb4N5XbCYun1MmYjNqtZfk#1#2AVyYjpD0Yi9BDx2ueMMiFwS04vs5~0^l&wKjH7q&RyM(mZW|_vsu2mF&EesCPiIkdA%wrrr98!dQ_R%PK=TiudY{%Eu1OCo~Z>pl0p6|<4S(xaqrd-J14FO$7cj7E@x9naDC=Gp4TCBytD4M!O6n~|;m+|}YJka9raAbsgy9fCx{S0{Sinm%~fywP`Ate;_3@4(5e2M@=On=vtKZRhaS}9PA9it80-Zxu0GeA!Pu0R7}ZgV(^O4zZ6Rzyx#(B4v&RFwrlV{k%yDezbIra}lTlyC?Ep=#6Ubto5QppER08ojCqj#Lpo-n)B1MJ*aaEnUyZtiN(KxDr_y%&y*d1!f7Hc9>YnuUPD7(x+9d<;U#)eWQSDD`waFL9hEJzEtD0z@;+HBOmOFQraD)=qdq}u?0GZ#Ut<jb@%@V$}yA'
)).decode("utf-8"))

_SELLABLE = ("STRAWBERRY", "MELON", "MILK", "WOOL", "EGG", "TOMATO", "CARROT", "WHEAT", "FERTILIZER")

_FRONT_RUN_HORIZON = 1
_FRONT_RUN_ITEMS = ("MELON", "STRAWBERRY", "MILK", "WOOL")
_BASE_PRICE = {"MELON": 250, "STRAWBERRY": 120, "MILK": 160, "WOOL": 200}
_GLUT_WEIGHT = {"MELON": 3.5, "STRAWBERRY": 2.0, "MILK": 2.0, "WOOL": 3.2}
_LAST_STEP = -1
_CLONE_CONFIDENCE = 0


def _public_signature(farm):
    """Compact public fingerprint for detecting a mirrored build."""
    counts = {item: 0 for item in (
        "COW", "SHEEP", "GOOSE", "WHEAT", "CARROT", "TOMATO",
        "STRAWBERRY", "MELON", "PASTURE", "COOP", "WEED",
    )}
    for row in farm.get("tiles", []) or []:
        for tile in row or []:
            if not isinstance(tile, dict):
                continue
            for key in ("animal", "crop", "kind"):
                value = tile.get(key)
                if value in counts:
                    counts[value] += 1
                    break
    positions = [farm.get("farmer", [0, 0]), *(farm.get("hands", []) or [])]
    return (
        len(farm.get("hands", []) or []),
        tuple(sorted(farm.get("unlocked_quadrants", []) or [])),
        tuple(sorted(tuple(position) for position in positions)),
        tuple(counts[item] for item in sorted(counts)),
    )


def _signature_distance(left, right):
    distance = abs(left[0] - right[0])
    distance += 3 * abs(len(left[1]) - len(right[1]))
    distance += sum(abs(a - b) for a, b in zip(left[3], right[3]))
    if left[2] != right[2]:
        distance += 2
    return distance


def _update_clone_profile(obs, step):
    global _CLONE_CONFIDENCE
    if step not in (4, 24) and not (step >= 48 and step % 24 == 0):
        return
    farms = obs.get("farms", []) or []
    if len(farms) < 2:
        return
    player = int(obs.get("player", 0) or 0)
    distance = _signature_distance(
        _public_signature(farms[player]),
        _public_signature(farms[1 - player]),
    )
    if distance <= 1:
        _CLONE_CONFIDENCE = min(8, _CLONE_CONFIDENCE + 1)
    elif distance <= 4:
        _CLONE_CONFIDENCE = max(0, _CLONE_CONFIDENCE - 1)
    else:
        _CLONE_CONFIDENCE = max(0, _CLONE_CONFIDENCE - 3)


def _front_run(action, obs, step):
    """Sell one premium line immediately before a clone's expected glut."""
    if _CLONE_CONFIDENCE < 2 or _FRONT_RUN_HORIZON <= 0:
        return
    orders = list(action.get("market", []) or [])
    if len(orders) >= 10:
        return
    already = {}
    for order in orders:
        if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
            already[order[1]] = already.get(order[1], 0) + max(0, int(order[2] or 0))
    planned = {}
    end = min(len(_TRACE), step + _FRONT_RUN_HORIZON + 1)
    for future_step in range(step + 1, end):
        distance = future_step - step
        for order in _TRACE[future_step].get("market", []) or []:
            if not (
                isinstance(order, list) and len(order) >= 3
                and order[0] == "SELL" and order[1] in _FRONT_RUN_ITEMS
            ):
                continue
            item = order[1]
            quantity = max(0, int(order[2] or 0))
            if item not in planned:
                planned[item] = [distance, quantity]
            else:
                planned[item][1] += quantity
    shed = (obs.get("private") or {}).get("shed") or {}
    prices = ((obs.get("market") or {}).get("prices") or {})
    choices = []
    for item, (distance, quantity) in planned.items():
        available = max(0, int(shed.get(item, 0) or 0) - already.get(item, 0))
        quantity = min(available, quantity)
        if quantity <= 0:
            continue
        price = float(prices.get(item, _BASE_PRICE[item]) or 0)
        priority = (
            price * quantity * _GLUT_WEIGHT[item]
            + (_FRONT_RUN_HORIZON + 1 - distance) * _BASE_PRICE[item]
        )
        choices.append((priority, item, quantity))
    if choices:
        _, item, quantity = max(choices)
        orders.append(["SELL", item, quantity])
        action["market"] = orders[:10]


def _terminal_liquidation(action, obs, step):
    """Replay-derived safety net: leave no sellable shed inventory at season end."""
    if step < 680:
        return
    shed = (obs.get("private") or {}).get("shed") or {}
    market = action.setdefault("market", [])
    already = {
        order[1]
        for order in market
        if isinstance(order, list) and len(order) >= 2 and order[0] == "SELL"
    }
    for item in _SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        if qty > 0 and item not in already and len(market) < 10:
            market.append(["SELL", item, qty])


def _shed_access(size):
    half = size // 2
    return [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]


def _move_toward(pos, target, tiles):
    x, y = pos
    tx, ty = target
    choices = []
    if tx < x:
        choices.append(("WEST", (x - 1, y)))
    if tx > x:
        choices.append(("EAST", (x + 1, y)))
    if ty < y:
        choices.append(("NORTH", (x, y - 1)))
    if ty > y:
        choices.append(("SOUTH", (x, y + 1)))
    size = len(tiles)
    for op, (nx, ny) in choices:
        if 0 <= nx < size and 0 <= ny < size and tiles[ny][nx] != "LOCKED":
            return [op]
    return ["PASS"]


def _terminal_action(obs):
    """Observation-driven final-eight-turn harvest/drop/sell controller."""
    player = int(obs.get("player", 0) or 0)
    farm = (obs.get("farms") or [])[player]
    private = obs.get("private") or {}
    tiles = farm.get("tiles") or []
    size = len(tiles)
    positions = [farm.get("farmer", [0, 0]), *(farm.get("hands") or [])]
    inventories = list(private.get("inventories") or [])
    inventories.extend({} for _ in range(len(positions) - len(inventories)))
    sheds = set(_shed_access(size))

    available = {
        (x, y)
        for y, row in enumerate(tiles)
        for x, tile in enumerate(row)
        if isinstance(tile, dict) and int(tile.get("yield_units", 0) or 0) > 0
    }
    actions = []
    pending = {}
    for pos_raw, inventory in zip(positions, inventories):
        pos = tuple(pos_raw)
        inventory = inventory or {}
        load = sum(max(0, int(v or 0)) for v in inventory.values())
        x, y = pos
        tile = tiles[y][x] if 0 <= y < size and 0 <= x < size else None
        if load > 0 and pos in sheds:
            action = ["DROP"]
            for item, count in inventory.items():
                if item in _SELLABLE:
                    pending[item] = pending.get(item, 0) + max(0, int(count or 0))
        elif isinstance(tile, dict) and int(tile.get("yield_units", 0) or 0) > 0:
            action = ["HARVEST"]
            available.discard(pos)
        elif load > 0:
            target = min(sheds, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
            action = _move_toward(pos, target, tiles)
        elif available:
            target = min(available, key=lambda q: (abs(q[0] - x) + abs(q[1] - y), q[1], q[0]))
            available.discard(target)
            action = _move_toward(pos, target, tiles)
        elif isinstance(tile, dict) and tile.get("fertilizer_available", False):
            action = ["COLLECT_FERTILIZER"]
        else:
            action = ["PASS"]
        actions.append(action)

    shed = dict(private.get("shed") or {})
    for item, count in pending.items():
        shed[item] = int(shed.get(item, 0) or 0) + count
    prices = ((obs.get("market") or {}).get("prices") or {})
    sells = [
        (int(shed.get(item, 0) or 0) * int(prices.get(item, 1) or 1), item, int(shed.get(item, 0) or 0))
        for item in _SELLABLE
    ]
    sells = [row for row in sells if row[2] > 0]
    sells.sort(reverse=True)
    market = [["SELL", item, qty] for _, item, qty in sells[:10]]
    if int(obs.get("hour", 0) or 0) <= 1:
        already = int(farm.get("hires_today", 0) or 0)
        for _ in range(min(10 - len(market), max(0, 8 - already))):
            market.append(["HIRE"])
    return {"farmer": actions[0], "hands": actions[1:], "market": market[:10]}


def _base_agent(obs, config=None):
    global _LAST_STEP, _CLONE_CONFIDENCE
    step = min(int(obs.get("step", 0) or 0), len(_TRACE) - 1)
    if step == 0 or step <= _LAST_STEP:
        _CLONE_CONFIDENCE = 0
    _LAST_STEP = step
    _update_clone_profile(obs, step)
    if step >= 717:
        return _terminal_action(obs)
    action = copy.deepcopy(_TRACE[step])
    _front_run(action, obs, step)
    _terminal_liquidation(action, obs, step)
    return action


# ===========================================================================
# Market-controller overlay
# ===========================================================================
import math as _math

# Per-step remaining sell volume of this field plan, measured over c27 self-play.
_SUPPLY = json.loads(zlib.decompress(base64.b85decode(
    'c%1Fr%Wm5+5Cza*39{~j!?(Ii3pWj#)PQRsXp4SH(SNTlZOK$D%hrRG91k$}ECK|GWl5pP5&z!5eqB9m??2xC_S${8>%g|40o8~KRn)i|T_c-Ng)B~CGN496wl}hgs1QXm@KJ@zO8JSLEoMTcp!~L+F{jWC^e|LF)=(2sf$PIb3(SlNzsDBEF#JfoWe(t$Yj9w9c;Cbw<7UNFSXW_+8eK!jXnZ0v6}ZhU25LvUVmLTB{V)npQt&Tu2T?{8u6>1DeP;Bfh-txjrG(rgadmg#C&QQ5mb7*zObT%PjIEHq#)0xwmcrH0IS6;r%ds_7fjeO<R-XVDHtFe5b{U9c@TIh4Qa~f2^712`IfKEUA#@B*lD={N5Gf8RziqLrKOgSyKR;|X>+lpP>YsCQadB~Rad9Oo3_rH(mxt||haX&ATwGjSTv-akk00C3!|SKjX7dw65Q*tshG7_nVVGkyprl}RZvx~bgg>YpF-fdKOSG4qgU%8bqxwVs6t+gzh!`qtez1P$MN(W?6824OUyMG5Y$A?9(^>?+g>mRks6oAK>ZeGxbZYtsodn6F-$d?$<E};~EL)F^?O7_S=&9^w^}PO$2eRE-I>Ru`&4T`{s6B{cFwQ{YZl6U*zQ14uWyS3#%h2Z*@^*MPQP3v8n8;y4cWAPRbdmZHJgFv)oG)UwHJsJsBlnMRadB~RadBm-FjM*T{4I2j>|PvW80OtT4e<Ic^F9%mLxt<aObni{eUSnSOm>`25B5IDhw)1T#~HJ2gbkb)it^`?XCZfm;OhyiIuT((rx*gdOtM5Af}2MpCW=~4u!#b8dq^Fe(W!z<VQjEXR6G?ub;2p#H~XpMB5DU|K3=`9*UzC3<m5IO40GEoV6^e>(Kih?vsxDB>cI}F?O-s7>4zgO*m=mOMPEO7fFHFt)1`zxoKzFEYZV<Sf2W`*g3~vl6)Si2btbe1*(mA?61N3mCrB|}<jgtQPJ>6GFRRV=>G|o`Y7^F*FlVr6C;{`%5t~lbSY!)lcb=RE!hfF_mzI-r-D(o354i67ZQuEZwrOsCA(S1oU{8hVL>-fNRvtUO?m%zt9OxwICh{0%a-kZ?nHV;0J{oL}oHQfG!C2wLe($Yu`<RKME{uGWj?HT?+Td1C5YbH5F*r?^*4GKtKIO3v+vWF6XxHyrn;6*2-<p>3c(Rs!pD~m+;RUgj8S*-S*aeT2QB@B!|NaA0p<>w'
)).decode("utf-8"))

_I0 = 10000
_PRICE_FLOOR = 1
_MP = {
    "WHEAT": (25, 400, "sqrt", 0.80, "log", 0.20),
    "CARROT": (35, 450, "log", 0.20, "sqrt", 0.70),
    "TOMATO": (60, 200, "linear", 0.40, "sqrt", 0.60),
    "STRAWBERRY": (120, 100, "sqrt", 0.70, "linear", 1.60),
    "MELON": (250, 300, "log", 0.20, "sq", 3.60),
    "EGG": (50, 332, "linear", 0.40, "log", 0.20),
    "MILK": (160, 122, "sqrt", 0.60, "linear", 1.60),
    "WOOL": (200, 105, "log", 0.20, "sq", 3.20),
    "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40),
}
_SHOP_DEMAND = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}
_CENTER_ITEMS = tuple(k for k in _MP if k != "FERTILIZER")

# Products the controller owns, mapped to a reservation price expressed as a
# fraction of base price. Everything else keeps the tape's schedule untouched.
_RESERVE = {}
# Sort SELL orders by gross value so the most valuable sale takes the earliest
# slot; market slots resolve index by index across both players.
_SORT_SELLS = True
# Ranking key for slot placement: "gross", "unit" or "impact".
_SORT_KEY = 'impact'
# True places promoted sells ahead of buys/hires; False keeps the tape's layout.
_SELLS_FIRST = True
# Only these products may be promoted into early slots. Empty means all.
_PROMOTE = ('MELON', 'STRAWBERRY', 'MILK', 'WOOL')
# Extra slot priority for a product whose remaining supply outruns the town's
# remaining appetite. Such a product is a race, not a hold: its price will only
# fall, so the units sold before the opponent's are the only ones worth much.
# Ranking purely by current price gets this backwards — a already-crashed product
# looks unimportant precisely when beating the opponent to the floor matters most.
_RACE_WEIGHT = 0.0
# Products that may be promoted only from this step onward. Selling wheat early
# lowers the price an opponent pays for feed, which can rescue a cash-starved
# rival; deferring wheat promotion keeps that pressure on during the early game
# when starvation actually bites.
_PROMOTE_AFTER = {}
# Products promoted only while the opponent's public money is at least this much.
# A rival near insolvency is the one most helped by our extra supply, so we hold
# that pressure on until they are clearly solvent.
_PROMOTE_IF_OPP_MONEY = {}
# Products whose SELL orders jump ahead of every other order in the turn, rather
# than merely being reordered among the slots the tape already used for sells.
# Slot 0 is priced against an inventory neither player has touched yet, so this
# is what beats an opponent that front-loads its own contested sells. Never list
# WHEAT or FERTILIZER here: those are the only products an opponent can
# BUY_PRODUCT, and their buys lift the price a later slot would sell into.
_LIFT = ()
# Step at which to pre-empt the base's own end-of-game liquidation. 0 disables.
_EARLY_TERMINAL = 0
# Force selling once the shed reaches this load, protecting end-of-day drops.
_SHED_PRESSURE = 80
# Reservation decays linearly to zero across this window, spreading liquidation.
_RAMP_START = 576
_RAMP_END = 716

_SUPPLY_DRIVER = {
    "MILK": ("animal", "COW"),
    "WOOL": ("animal", "SHEEP"),
    "EGG": ("animal", "GOOSE"),
    "FERTILIZER": ("animal", None),
    "STRAWBERRY": ("crop", "STRAWBERRY"),
    "MELON": ("crop", "MELON"),
    "WHEAT": ("crop", "WHEAT"),
    "CARROT": ("crop", "CARROT"),
    "TOMATO": ("crop", "TOMATO"),
}


def _mshape(func, x):
    if func == "linear":
        return x
    if func == "sq":
        return x * x
    if func == "sqrt":
        return _math.sqrt(x)
    if func == "log10":
        return _math.log10(1.0 + x)
    return _math.log(1.0 + x)


def _mprice(item, inventory):
    """Exact port of the engine's market_price."""
    base, throughput, below_f, below_t, above_f, above_t = _MP[item]
    if inventory < _I0:
        amp = below_t * base / _mshape(below_f, throughput)
        value = base + amp * _mshape(below_f, _I0 - inventory)
    else:
        amp = above_t * base / _mshape(above_f, throughput)
        value = base - amp * _mshape(above_f, inventory - _I0)
    return max(_PRICE_FLOOR, int(round(value)))


def _remaining_drain(item, step, shops):
    """Units of `item` the town consumes between `step` and the season end.

    Shops fire on steps divisible by 4, the town center on steps divisible by 12
    with multipliers that step up on days 10 and 20. Still-locked shops are
    credited from the day they are expected to unlock (one new shop every three
    days), so late-game demand is not understated.
    """
    if item == "FERTILIZER":
        return 0.0  # neither the shops nor the town center consume fertilizer
    unlocked = set(shops or ())
    live = 0
    pending = []
    for name, products in _SHOP_DEMAND.items():
        if item not in products:
            continue
        weight = 2 if len(products) == 1 else 1
        if name in unlocked:
            live += weight
        else:
            pending.append(weight)
    n_locked = len(_SHOP_DEMAND) - len(unlocked)
    pending_total = sum(pending)
    is_center = item in _CENTER_ITEMS
    total = 0.0
    for s in range(step, 720):
        day = s // 24
        if s % 4 == 0:
            total += live
            if pending_total and n_locked > 0:
                expected = min(n_locked, max(0, day // 3 + 1 - len(unlocked)))
                total += pending_total * (expected / n_locked)
        if is_center and s % 12 == 0:
            total += 4 if day >= 20 else (2 if day >= 10 else 1)
    return total


def _count_driver(farm, kind, name):
    total = 0
    for row in farm.get("tiles") or []:
        for tile in row or []:
            if not isinstance(tile, dict):
                continue
            if kind == "animal":
                animal = tile.get("animal")
                if animal and (name is None or animal == name):
                    total += 1
            elif tile.get("kind") == "PLANT" and tile.get("crop") == name:
                total += 1
    return total


def _opponent_scale(obs, item):
    """Opponent's expected remaining supply of `item`, relative to ours."""
    driver = _SUPPLY_DRIVER.get(item)
    if driver is None:
        return 1.0
    farms = obs.get("farms") or []
    if len(farms) < 2:
        return 1.0
    me = int(obs.get("player", 0) or 0)
    kind, name = driver
    mine = _count_driver(farms[me], kind, name)
    theirs = _count_driver(farms[1 - me], kind, name)
    if mine <= 0:
        return 1.0 if theirs > 0 else 0.0
    return max(0.0, min(2.0, theirs / float(mine)))


def _reserve_price(item, step, obs, shops):
    """Reservation price for one unit of `item`.

    A fixed fraction of base price, decayed linearly to zero over the
    liquidation ramp, and scaled down when the town's remaining appetite cannot
    absorb the supply still to come: a structurally oversupplied product is a
    race to sell, not something to hold.
    """
    base = _MP[item][0]
    frac = _RESERVE[item]
    if step >= _RAMP_START:
        span = float(max(1, _RAMP_END - _RAMP_START))
        frac *= max(0.0, (_RAMP_END - step) / span)
    drain = _remaining_drain(item, step, shops)
    supply = float(_SUPPLY.get(item, [0] * 721)[min(step, 720)])
    ahead = supply * (1.0 + _opponent_scale(obs, item))
    if ahead > 0.0:
        frac *= min(1.0, drain / ahead)
    return base * frac


def _plan_sells(obs, step, slots, short_of_cash):
    """Choose SELL orders for the controlled products."""
    if slots <= 0:
        return []
    shed = (obs.get("private") or {}).get("shed") or {}
    inventory = ((obs.get("market") or {}).get("inventory") or {})
    shops = (obs.get("town") or {}).get("unlocked_shops") or []
    load = sum(max(0, int(v or 0)) for v in shed.values())
    forced = load >= _SHED_PRESSURE or short_of_cash > 0

    candidates = []
    for item in _RESERVE:
        held = int(shed.get(item, 0) or 0)
        if held <= 0:
            continue
        inv = int(inventory.get(item, _I0) or _I0)
        if forced:
            units = held
        else:
            reserve = _reserve_price(item, step, obs, shops)
            units = 0
            while units < held and _mprice(item, inv + units) >= reserve:
                units += 1
        if units > 0:
            candidates.append((_mprice(item, inv) * units, item, units))
    candidates.sort(reverse=True)
    return [["SELL", item, units] for _, item, units in candidates[:slots]]


def _cash_needed(orders, obs):
    """Coins this turn's buy orders require."""
    seeds = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
    animals = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
    prices = ((obs.get("market") or {}).get("prices") or {})
    total = 0
    for order in orders:
        if not isinstance(order, list) or not order:
            continue
        op = order[0]
        if op == "BUY_SEED" and len(order) >= 3:
            total += seeds.get(order[1], 0) * int(order[2] or 0)
        elif op == "BUY_ANIMAL" and len(order) >= 3:
            total += animals.get(order[1], 0) * int(order[2] or 0)
        elif op == "BUY_PRODUCT" and len(order) >= 3:
            total += int(prices.get(order[1], 50) or 50) * int(order[2] or 0)
        elif op == "BUY_LAND":
            total += 4000
    return total


def _race_factor(item, step, obs):
    """1.0 when the town can absorb everything still coming, higher when not."""
    if _RACE_WEIGHT <= 0.0:
        return 1.0
    shops = (obs.get("town") or {}).get("unlocked_shops") or []
    drain = _remaining_drain(item, step, shops)
    supply = float(_SUPPLY.get(item, [0] * 721)[min(step, 720)])
    ahead = supply * (1.0 + _opponent_scale(obs, item))
    if ahead <= 0.0:
        return 1.0
    glut = max(0.0, 1.0 - drain / ahead)
    return 1.0 + _RACE_WEIGHT * glut


def _sell_priority(order, obs, step=0):
    """Rank a SELL order for slot placement; higher goes into an earlier slot.

    Market slots resolve index by index across both players, so an order in an
    earlier slot is priced before the opponent's matching order in a later slot.
    ``gross`` ranks by revenue at stake. ``impact`` ranks by how much revenue is
    actually lost by going second, which is the quantity times this order's own
    price impact — that promotes steep premium curves (wool, melon, milk) over
    large but nearly flat staple sales (wheat, egg).
    """
    if not (isinstance(order, list) and len(order) >= 3 and order[0] == "SELL"):
        return -1.0
    item = order[1]
    try:
        qty = int(order[2] or 0)
    except (TypeError, ValueError):
        return -1.0
    if qty <= 0 or item not in _MP:
        return -1.0
    inventory = ((obs.get("market") or {}).get("inventory") or {})
    inv = int(inventory.get(item, _I0) or _I0)
    unit = _mprice(item, inv)
    held = int(((obs.get("private") or {}).get("shed") or {}).get(item, 0) or 0)
    qty = min(qty, held) if held > 0 else qty
    race = _race_factor(item, step, obs)
    if _SORT_KEY == "unit":
        return float(unit) * race
    if _SORT_KEY == "impact":
        return float(qty) * float(unit - _mprice(item, inv + qty)) * race
    return float(unit) * float(qty) * race


def agent(obs, config=None):
    """c27 with its SELL layer partially replaced by the market controller."""
    action = _base_agent(obs, config)
    try:
        step = int(obs.get("step", 0) or 0)
        # Liquidate one step before the base's own terminal dump. Both dumps hit
        # a market that only falls, so whoever sells first takes the un-crashed
        # price; an opponent sharing this route dumps at its tape's step and gets
        # what is left. Nothing downstream needs the goods or the shed space.
        if _EARLY_TERMINAL and step == _EARLY_TERMINAL:
            shed = (obs.get("private") or {}).get("shed") or {}
            rows = []
            for item in _MP:
                held = int(shed.get(item, 0) or 0)
                if held > 0:
                    rows.append((_sell_priority(["SELL", item, held], obs, step), item, held))
            if rows:
                rows.sort(reverse=True)
                action["market"] = [["SELL", i, q] for _p, i, q in rows[:10]]
                return action
        if step >= 717:
            return action  # proven terminal controller; leave untouched
        orders = list(action.get("market") or [])
        keep = [
            order for order in orders
            if not (
                isinstance(order, list) and len(order) >= 2
                and order[0] == "SELL" and order[1] in _RESERVE
            )
        ]
        player = int(obs.get("player", 0) or 0)
        money = float(((obs.get("farms") or [{}])[player]).get("money", 0) or 0)
        short = max(0.0, _cash_needed(keep, obs) - money)
        sells = _plan_sells(obs, step, 10 - len(keep), short)
        if not _SORT_SELLS:
            action["market"] = (sells + keep)[:10]
            return action

        def is_sell(o):
            return isinstance(o, list) and o and o[0] == "SELL"

        opp_money = None
        if _PROMOTE_IF_OPP_MONEY:
            farms = obs.get("farms") or []
            if len(farms) > 1:
                opp_money = float(farms[1 - player].get("money", 0) or 0)

        def promotable(o):
            if not is_sell(o):
                return False
            item = o[1]
            if item in _PROMOTE_IF_OPP_MONEY:
                if opp_money is None:
                    return False
                return opp_money >= _PROMOTE_IF_OPP_MONEY[item]
            if item in _PROMOTE_AFTER:
                return step >= _PROMOTE_AFTER[item]
            return not _PROMOTE or item in _PROMOTE

        # Only promotable sells compete for the earliest slots. WHEAT and
        # FERTILIZER are the only products an opponent can BUY_PRODUCT, so
        # promoting those ahead of their buys would lower the price they pay for
        # feed; those sells are deliberately left in their tape position, where
        # the opponent's buys have already drained inventory and lifted the price.
        # A lifted sell jumps ahead of *every* other order, so it is priced
        # before the opponent's matching sell in any later slot. Only worth it
        # for products the opponent dumps: for WHEAT and FERTILIZER — the only
        # two an opponent can BUY_PRODUCT — a later slot is strictly better,
        # because their buys drain inventory and lift the price we sell into.
        if _LIFT:
            lifted = [o for o in keep if is_sell(o) and o[1] in _LIFT]
            if lifted:
                lifted.sort(key=lambda o: -_sell_priority(o, obs, step))
                held = [o for o in keep if not (is_sell(o) and o[1] in _LIFT)]
                keep = lifted + held

        merged = [o for o in sells if promotable(o)] + [o for o in keep if promotable(o)]
        merged.sort(key=lambda o: -_sell_priority(o, obs, step))
        rest = [o for o in sells if not promotable(o)] + [o for o in keep if not promotable(o)]
        if _SELLS_FIRST:
            action["market"] = (merged + rest)[:10]
        else:
            # Keep the tape's slot layout: sorted sells refill the slots that
            # already held promotable sells; every other order stays put.
            out = []
            queue = list(merged)
            for order in keep:
                out.append(queue.pop(0) if (promotable(order) and queue) else order)
            out.extend(queue)
            action["market"] = out[:10]
        return action
    except Exception:
        return action
