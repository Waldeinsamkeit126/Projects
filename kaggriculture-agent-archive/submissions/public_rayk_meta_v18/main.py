"""GiovanniCR episode 91533875 player 0: distilled trajectory with the tested c17/c27 controller."""
import base64
import copy
import json
import zlib

_TRACE = json.loads(zlib.decompress(base64.b85decode(
    'c-rk<O>bODj{Gk=*TGdKf9*|e*Nlx(w+vaH!fZomG_W&RU@?2>-P>aR``VJ~>oFJ%lKCXt-KSQ|rC0efnVDoT82tJF&i?W1Z~y%JZ)gAZ^Vx@sj~~x&7ia(Z>wo{p|9t+%=O6$1>u>+{_y7I;^Ur7R-d}G%|116Bhfja|<>IIJKVDp(EzaItZO;}<^XrfAHk%J;i}T$-eB5l_e*X3L-R9!vZ1H^Z>mN6lS3e#7`os0r+fQ$9j{o5HUyGBsc>m@vpFSLY|Neb`KHF|S-rNmz|HH#OAN|>We8;cveaFKfPQT@+tLvM0cMm=MWWVR(PwDqO3{!pf51-y&zWwF%|K5E1vLNKalTYfSzr1*}*-sLkqK8j@S%s75fBuJ`ZuTqde9xbbje>p6=?72N`r>AD?LGg^MKD44AHegndxPDV9zFNrLu_6qn+!efF!aLG+Alaf4w${Zp!T`@r}+~iFQk3^$E!~d6AtDhTtI)G4~A!_qq2TSqx0vXwSN0k%g#e*{ger5te-S5m37?xEtrn`7pOh%U~ki3)t+akcZfBx*Kb+F?jf6tfkvRr#$X$`{~_@><mZIfL1<}jt}ZV(Z*G41)8_i-{pI_AzZ<5#Pg1vk;o3sOAP?Bxa;brWZw&_;%uaIHyS+PdfhwE7eqj9ZCx86OSM(>RXX3}r<(JUyXs6sqWH<seG1`mURQ$B}LgJIhcmHjiwWu9sCLTJS8u-G?+vHg@d5_NRaJUpJ0|n<l9J?|?|1QB}jQ`wBQ+UYl{DZ;M1STKPQe}Wse?MgeM^RJZtL+3AhH#i*GXi;j!Lm6M91f60mW89#Oi|$(`x&x-tIiO3D4wA5ZSi~g+v-(!a_60*n9IqpKi*tlY=78XU;piFu`XVQlOKj(ileT_r@1J*SLQA}JzA;mn@FM90sxieD^<TY?BMLNhG(Q5R!y(p);$5@K6(+4cmV@@W@iX2BEmZ3SW@wj4(3sM-eF)a{yoUe^jr_k39<gd1QTpsw)Ws~0jT02C!kyB>igp%V;<7;3tAB`ITNSp(m(G0QQ>lL@X3g<IA#++7eh2Bkp5!57uSC+Twq`_$u&_19TF}McqmAuRf6Pch%F80;egl7`6(7b54rcFlV1GrX&iyu>~}tg*YX`mc)q`tl?Blwa+?m7S4m2RRo?mgzq)rP_sctHxEAI+<R(4(Kkw0%>XFj)`d?+7g9hY)e1tdzi^J1L@i?B^ML-eeBlru19p*a@@v-eO!iFLOz9p)Y9UsCT8z7oy^&PCQaJVn`SJM3ty-hTI><C!LK}8+`=}v^=EGIBFJMi}XpZgc#{8L)NGuTr$Bj616wIBQKzEVtKoyQauUmbkS*X0`=$0IR-G6N2g2`7CRVu(kRzy1>02ZjJKSYy=0gTQk*{?Xx_AV;R|1?UN+N0|C;W!{+|lW;xkW3VBF4|;oj^&zkW;$9sB$*Zf&hm#td;OkxV_xbjEdltKP7HmLYO`_1%$Q<<UiJ5~#cS(5=x_{2z*z_lpkmc}LgNjW&iv%s(i)BEqNy0#ttJ0>73XuRV?GZEJCGh2L&n)StQ7X(*_{^#Zg53S_8e5{4Mv)UZYqCpU>x9Z~+GhbXRC0!A0DPnVG%L)5zE>qi3>m2o5rOJ9-~E`&rv&bwGds>}*dxDUUDLy#&cFh*Ejo@`U|y$}1v*r6<eOTYL82CK&6qt6<{0n33N4LnJ45-V2s*W2=`B<%Isx_^d>^#vjp`o&7L~DCU;@7LoN##*5;8zPBe;=;7j+nxBv`fc4o%|#I+Z;VC(a=@44d@V$b(wplyjd7j4~;dAPBB~@MLv}JCZP6SW$bjYtUo&4)+cjK76R~jWOR3`S|GLog6gS7vS5)Yovn1GNgDhTVC2NKAjgMK2BgC0-2Fv(*lPoBU8#epfY#_abUTC$Z<fmas#TB?(<5a%;CPabJVG*b-wQS{N7Kj?(wf~2UO>(;Zr7%R4T}D2xMKTSpuLCM_w=%5c05UM#1A9GfGHjn%OvnsK+>U0&7j8JXp7J>J|;k9vp5xXBIN$c?x3{xW;ZYocpd|6&-Ku#H1D09Ps~v%X;`WGxu)n92*bIPlP_?elb`*Y2pjf77owZ(1<{2=br{N!p+o#l9S3OKe|}QemWF;s-8|@_QBp7Le!kz(2IZ%+i{VZ2oFPq8tySp&JA|KeMO<MU-U#S{_@$8kN@NQ%fEcV{EgSYY^P0H9{tL3c(_N;!hy)S7w~e)J;#iZjAts403>gCCSI#b9YABW7h7da>#W;|fU4*s9KdNQa6_V)FFvp<6q1SAlEb@>c;+c5f-}$NWmL>TUB-h!7tE!R)BvUt#s?s&Q7L{Uyzej*7DM)C%eY*S&}dt4x&IE}sS$e|uu<3)pco=DL9-5nis5-M9GIXXYb9lDY{CIl&WX9$7CK9!$7Ad4sXdw>jvvj!pK(NFX!bL3<;nL?lx=1z1zQAaH}ie%+$n`wzKAihUO35w1A}pJh%wtF3?YzBWykvg5;*hp0Li9mK?a3=Xb4Z=k-XBrF&MnhAn%q1*rRCc`XPjJkoEq1+_h0?yM1RH*7<epj<>k&#mv@evQoo`;ie+KsepHo6BA##7d8T6X{xPn5$7XeZf#vy?k^vLf)^0bcl$cP^>j*h0MV*~HLI?H-4bB*P==oLFqjFq2Gae3D-@m#z&}PWOV?*I6BUVO_)dU$jr?jqesvg6nHXcT$V5OAZx%wpIT+4EO$v;NoO-8CT%z*ezr4V1&1=Guc;Rv+6w)M6d3UHeA~8#5#<JzN*%i?8AZ84v7$qsl079N#ei5Q9N<5tm>52V=Zwrwv8A$|3>3);=*aUv1XhR&Y<tx41Vg}16$;Qbi!9+1vK%A+jwMK_B_kmnm#__-18v$S4$`LML**?=bc&`9q)6k5hq+rt!wHu9gS7O(rELyM<;7x9mGEa1Wyb!!0`%ZPs6g`PThC2Nk2?5J-My9+*xMG=0K<EEcDzk5H36{cRAb<CKf)OQ`j|uf@;NM8RPNXP9ypDn<T50HcgNDklr5vKuMBmU*GWc6|WOD;+QS~PP6&PB8Zm{w@5rl09R>g4SNh$nNm=|SKPv9-O>#m2c2Rk?k@V^2AKc&>i>Z0WuA7;09ZF6Re_8PFOqU35w6PA{E5p2|!iYqKaGYiL^d?L+JVLh|ejrWm=b;R4<4(#yPyXrh!IzU<Y<ld^yP>6Tsb_1i#^rU?vRKOE;!FJY?2SO=V$>1#xF^>*41Ev!x7PkRvvG6)yPZ`oZB5u<dCU%kxVpVh=jkUo-_@^DjS2_`x9>2QnC_q2^#v<N`<wBIH^TN<;f%6aYfJh{ghsgGCkC%Am{>xGip<mr90+)n?&%+Ko4KDd*R4GA{Rx8kQ9=*OmVdg$n(2o`pWaKobfM?Oi(2f<`O$0{JVcY-R=|<ENNpQzi>z2JbymH`~mP>^b1ev~)@Jc*?L~Gn@ospmc^C)1PB+Qo380d`Ik0<0(KoXNs67?y<yo^k5Ti@=s^ua>)53!0&Z#iOjn7jp|C?21W6&)hG0&@bhvZl3OH8wcq*e}u4+7Mn#=FH=HR71(4t9j~$xYtBaii|{n&La8_k#=#khIu?EBx3fzH@!DVqEbmg%B5&zg$r8)03*4iw#Z*D^}Vcwtqaa*442W$Qx~IXe-I=&eqRrA?g;e0HudQ1P6)m_76N{#L|J`{l_qmEU+UM@Zyh<0bbWnK`AGfg@zcv+N0Ek>ZX?jc=p1o3*QR#jXjoYaB1n2hOkk@5)WZ@K$Woov%$R&Cd%=d0k%ZPj%5YBy3570<6<R|W#G-7TOSGX##Y1JGO@i{8$*_V^c<%zO(tf6KO7j|ZbQafAtGU7-Y9NH@PpSU})iu=?sn<QGgkDrUA(Vyr%IU4&VFSOxE!kM%TCMbJh>Y1cmg{`lZycG%w0dBsfa^5cI{%6SD!F2RzQ_th>y3hZKYKZ*-H-ct;06T+g9+$dXyLL2i6WW0^;8{R?4TL1s~38$`wf7L<?!3Mwz|f~<m$`Ge=Y5d<6876ExE|%_7jt&Y!Ft}src8Ap`2!SMjVzA0g0d*QyVjC5aR*;e$D}88g=d0Oo)dVejA<IID;?Gw<Hrg89x=g2Z+BPP@M5-jecSPjHPkd;?=1hO!+6=v*43t?=)mS#mEwecna3y4e!+DUB}LAN<9!!iaimeRHVU3(EjEC`LQ9(DTJknbS&={TlvhnpVdJUVWBAPSuFHzO<=FScP_XgS6Q45eqRAS>qa>I`upJY&d1q}^NH(HS*yd*O;@*S)Z7tjY>l{_rX8I)e6EmJ)@lZ^Se88u5_@xm>8ZLfo*>PKPKu<nbX%7S5gW6b+&P){BG5~#8N>Rvv&*by;9N81#9{|2<wnZ8j*H+(SV1PMA=4uRI_rMwp<8Z$S!CZT%*UVrA0Q_ggo(+~k<27j7X#;I6a7VcNUDyO&}g&RGoDhDv3wmGOy8>MMA1aL#`?rro7++kGCVJPAsgO=i514(`@c4q1Q^^5jIw2>)QzN}e6DbK6RwF0pLJS)rQ|K#Tnj6Uht{-est)Z9h;W|0fR6A$U&VY+#yU1pw@tUSl&Gw2ORQXhwpNa3UzCE^<IL^y9E8Nr3{m#gx0uaM>aQP1q>qpY9>cMPk?`96mr&px{?&7#18%|5h{E~Q(dXY|HR13~GCIL%6F`EmA!V)g=;9ey_BNIFNA=WpLMBr$v(?goyr3=)4ij$QF&908<pb(qltdidfQ%%}NvsCFS5}F~6Fdp^7pYUWkWrzL0m@wB=%!#t?c#x`(3>`VVCR8QELV&F9kpONPmgWV-Dr$jQPIhfstM5!&Gw;49CckFh9bgZ!E@L*q1WyW5%<gjD1?Hn%0VP^9kZU91X_!9pw-N?lel0|02s%U3$81jpFsIp!{{kO=jE8BfS@MjJW^Dcv_80Yw*X@i+4MQC2oeJVJo>beF)1*z{RP<$CIh)uI#;_nrC^mLb+cI1ZMS+d2{P=nQt|l34&Ve60xU3v%_1~kX)=RS)$@l2F46IwRSzdZ=68tPYAFhtkLhpz#H!_}a{Nfi9N=l+WI_33)<1Lv&gDXgL3O{`9^77lQ!M{g)Tx4~X1jShU1y+nBybD2y^Q~|Bu_4A^pI+fLY?Rk(F0vi3Yk)`-5sDJyIvlpNRjH|$1>0@B_hz6y2133l9Ga9O3eBM5si@)*a;)j)W-H2kMyD97?2`wmC0fbzK;O%9`+?_iORa6Oof7kgc2x%?+llUTpI8NV}yj6dZ16q$T>638Syg`W?q~s>xc4s9}Ldh2;eBX91yKXyjXHpPSB9_24sVgS!KS1#HOx@->?x={X1WOU6JN1&LOK?kfqo&JTN;L2r(!;4*vO&<?*`B@>p4F&1=j1SbrZRj}v9`kMA~{4@{eU_0-zr2r_f28x^f@NY(D}&9<8{6pN+=R~A_wP6)9+Ku&O+@KcL~kM*F?2)vLiM4rn=REQwOy446O6$?R2nZ;}m09<IGMAp1f(a^pCj>a*oQqI-RcO(e%-2(Du0l*`VJHpSw+hVv1SU6R7Yo`7IJaS0MJSMY+L-ZlB*$crwKTS$4u^8W;ig#N$lcgg=N!LC|M>XhE8tP?wPK8~>mQT=C7ivS=NCrY!G_`!R&qmbFYq(1YYG9x*aAP}l_0lXunFQe^K)mRF&Ar&b9L^BHxHjYFcF}kRMSq;N{|IHv2MwL}yHh&q^-+&OZ=wYC&=izD_XQrpYezF4Dm;|mk`yZ~JuSq0O?j6ra6G6dfmnu?&v53zY5;S<*CH$x(9q-7EkkjtVse@GIXbN?NKs0mVn#j#fMn97Uun2cDX&jEyk=D|fak{kVm5k&uFi+nY}eJ8LMXh-zt5t8#m7RGj9w2!Gy+gWy_*%Kez~aoD3#SX5U&zLF$IkJ8n(nEIe~+<DceZkU#;3a3|Yw}=ab>SCSahd6tW$t(qgXN9?r4~brJZaRMv$z#kPYEPdy@~$+5QG-Y<2DO0~$!m7LK6KT=}XpM9VcMBIiz7${$yS<ySK+>_))CTA1v{=3a=0R~`clebY&WwAq_P)Agipq18NcWY=_P{6aQtxJ%3Epps|`z+0ra=&MmM*z#irnfZ3CuLt!i@@&E)V8LLRusg2&^`c1JanIE;Rx%_XrZeL%`A!tL+iK1uAJ)V==L&F<Hpnv_Yj*R_0r}MJu}!A6p&ed(^W7{0h#mXvjSp+TZwS=>v>TxW{wPNzV`?Vc38^1(y7`qHWQuFwc9V>^kPJvf*y~PxbMIjRXT-7JQ(`PS(Rk;!pk^Ky=k>Nj^>ES(j89l&E?fkKt*h;&;<iuEX}6Ue5Ro?Go+?F-l9-Nk@nfBFcebjCh5|E5Zgj(OqW23=p4_vK=wNy1k595R96BD{OXYIG&2ZngLrNaYrGVC>9VUV#`{9V5K0OACsiyUmuO|<U(Vho3Awm2o-tXHsKI2o6}A36zK|x#`H5fzJBmiXkpo8%!8q^|)EpJOqS5^+C%B}P3&)hD{o>~=m9xfEg5%y&M->B_wMniXm6w(4M}zm7j)W8VJan1Y)dqRnq)cBNfdGq5(ox~ZnHNUJi=Dx`fePhoKnhs7as@TMK>LY@p&0>vCJ2p8rvOvSJq#>bx6LOyxek0lT+4#&IXJRVj>sB`@6Ra9Z=>%KNNhq19i=GS!w=Ka&TkWMM~H}_kUae4$p-|1Bg8WY?`e;TPIu!I=H3Z%dIEdy9dm<w-ovB6cbV*JMdh2T?E~Eoo*wzeQ5M=ft_BsF99IZ%(077^=g=J#we$erWrq<rf`=Ftg;4^VMspjkrNsMDrEt{+7mkR0o5WrkC&uJgs7B75=m&a2NyFP>5%NgL(u@FRO;5T-!GtFUZTh8GGVYj0yZ?&)bQ<02lpbIqk;l&Z51-y&zWwF%&35zYVQKfY(r$Mc>DW-3*I-iUo6Y{>$tb=KX=>e8#==5W8SyWt#)x7n^1-Rp3Q_h{w5I}Ki(wsR4~Fs7gFAgRc5C&##T$?I_P?}@Y!>!At1;;h6Zm|~X{3I)Exx#X6dHHlc=rMzl<-;D8p|wtv8~Yc5Su(o=2K8ckiwT5y7%h+nRf<65gCt`HP&iqWq~4S+C{J=mnbDaXj{GnQ|FmpvKAfjR1#m*tLFmyth%8<y0eC-_lk^qW}K{rdxkW08dTMZ9Dh@KPXM&h17ssL9!x9B1UhO4IwDsnknM^Yd$eX$iq#Q*C3OM>V@j!mbt#7Ku4WTCN1OG2Te|fNT10z-!F{uM+Z=t@*W+tuHSA^x-H!&P-a*d!aU*K$c*Z9QiwzOgDUkB&$dBqcYcVN+a`Z4%Rw1KB&y9&!tQch-gOpc9xF2iKJd;hCLK{sSb+{cvCJ2e0g627-0<T^<o#@J*DhZESd4nsz6^37wi`I{lIw~v*g6j|}4VH-Bu6#&<yObsE11r`?l)2?d0lA=GPGZGb4+yQA-!RgmgO_!MRN3W;8!yq9O|3~r9IamAF^@hSekSFNmFP}UrZK1@iCPErB)=tDNq-L}$(!N8R5g217_N5vuUc_eaUYN;hOSgIE|kVlu(IKU5X1WAs$W28<ND?5cTy}E#P#RJxc+&SC*wbj=v1;?(-3vldNl0^D{S<GK!cngA{RJPk_?}ZC+PU4U=32h6I?kFu`;F#G4}>CZ^;Eop@uLcbV|&qtX5(#Nn#Jxg2u}FDGA(a=TnK-5pkW=YNM<b&(ND)X}l~dvoOiFNRYux=tS$c8Us+I+-*YhLSYI+zmnAdQtt~}#6T19k<PDQpJQ!(=<bs<pRSBjj8A3T-cL+^{Qk_cCWAJW0)KCz6|uD&q!}h2+B=qk7|J*x;hEf-l7R2G%H>4Jf5qbc0Q7UMA=eW?L%3+?j-b*_r8QPh6Pe}005BOdvqTn#zUoH@(_f=45fkOFswk=bp>{?Pb3^BV$hr@ZZ<=iL4!z-4Cut(k7q(<4>v{q92Cww2U`pgzj}W+2c|CX;`^F|{Dq@|42t^gTHa?+;hAy^-vNC?wE;B?ki9i^B(DdJ8a^fpTdVjfW!-FScVs4+p`w@H}jSBPppJfpzT+<4&wIG?#n;UxNXQ}H@)T)mKV1pAfKQalIq-Q;I1BF&WMbAlKc;`4m=+jX;wScE)x_}i}L7u+XRF%Egm@sl6sQhoCU!lYqaqTdT&{zQg(WBFYK#>@glVcakcl63MpO54pX6cy*fp~(#l0m}6aIn;oUMeLiz(i%;Wk>)|_7tqb<tDOBpyDI!C*(iS8X8-frk!P@TBWk44*rgmdUW_|XagW@B~K`BMj%<XQJNY~D%{Qi(_UE;UEoqLZ~={tjuj3#6+GlG2=^E32ZAaR8S99dsG`ofD?rqAPMAEKh)%#c$J{EtIxODsnpB?ByM>|6{!$5cvyfbETffW9DX4Iu!UK}n6pXN6IKlfmr2!kD!nAhR7g7c0C3XNjp%~qknqDYvTZ8BW;WbSJk|kg`laHZDTIa~Xs!lu3)f*|EJL?EKIj&!RXZlJt1c)=m&RYsfYfS)&0q>);-XiTw8|xrFp_cMdeSlvlfr|m>B7v*h0!yX%7xX&om2SC;$7)2$90fHiE0o3s?q{aJgmW)x{-5eoZ`;f&NvAl`nMliL=HwA#V007(im8Z_(xWCU&9dKW{Z7QHVA9^5-kU{fd8zjsjXKL5Np(js#k+K?2URPt41&@FBVr{eKM$iAD5ZjW9TnTnJ*}iz!mv|u$N>hO9%d*Df|J*1H!A``3e$#X2ox|&zA9*E2S63zUG+55#<b=qqu~TZONywK!-ECV*L@PGbtR5es>5V2-Ut$WT^G-@VX+Jp`0pmLI31FKL*7Zdrlab?@G(RR?H;kVPvAGX+CNI&-=btdIWE!eCRt+XpKn^`XF73ns{gba1PZFyrG|M@EbK!$TvwR6`=eZYI26I90b{%KQs!0t*~DtKpmc<`e2q@wp~^oj0~)$DDe`<@_=k(*B*dC|&3z?QW!kB{+Kq~SwdAfNBlf+cN|!#pcn0iBbQj(h1T0z0J)5(Plb^yU7sFd$BF;_<<zV@69~&q#i~{71(muSCWK3eiF#XFKv+Q!p8?uz`5Vl~<<3lHpy8GsCl#mnaB2^o?POREXE;9rc9h4O4kRr3A(au3(YSd~_!2Jr~fm{YELq%t$V?qUTI*doX4Bdth35l<uBunKAtTId!1+=txD%qBkDwz@YJ%=Q#^iT<$4RwP_4Sg#1<$zx}3`Ap5YMOFGORFfyaz)R)S|_Pc>D$LGW+A75s=z!og>e8vIYf<PtR<|qrppb@$k0;>a@1ge{^;k3=xCt|g;P|5K%+!Qb45r>ofbwhe!#F^Q3`5RZ&S?006P8T^gxpmzvy!H6M$NGIz3036RJuTB5D|AD3hGvr=XO)-47`gk_wk9ux{Gmkj{9~Yg5`YHEc0Zqv9nyl2TXC6ln{0jR`rVge$C=q`7?7>RFduCf$)ELPs1^`q5=-L=wX*c`Nf2j8=SLD=DIrRxDfe4KymjaeI-_*p?UXv+3UxF~S5wL5ytjg3D)_DA&n@BN_%1*HEbo;mE>TBt!I232XJ624vkKG-#<OSY1hO6l76cFch`jI2c~NWsz6{vI`WS3uPfT@IKy*FP|*v7V2f@sT2vDbD<uDg22bh{Uwb;sdj||wt?U*Zt}rs*ffw3GOSH$&Y+TvSCu3(V?3xu0v;Z$E>z{vsJ=0oG;l!^q^o~a$>1H1rNH{5RG5N)UT7lC3oJT~poGkGM0wtdi546jF*isaq7r?F_3q5?OSm5uKD^%~P)k$wumQ&SR*#^#Af3rJOaqO(1kuq50sk4^GP;sMQk20+c5!J2Hp#kf3TGY>*~Q%QqiCDC4N4_Orj!t5MmYdLlhQ(8#1!>6;;A2zC3Z#{(cFW&J}IVM-)2U>`Iu-q8pV{YNmS)4InlcWwAf*p!Nj3elzuHt4v~nIhEXhH96lYDO!)ZOC`9K|1dcf)FTLEejex6qm|pD56j_+wt|nT@zZ>GYjMc<B;%>ve6iyljowQGje^I0c!BBItMl13CcpYfdcQ`Y`z1@TSl=lo+?n<;;B7w={)S0Gq9IU-$eq4QkAtt};m7hYcRP7O{rH;`CZtt6|To<6%|5l)Zu&_B?L?!E3Lo1>nD;RI7KdMRspeZ<EycGDWMpGdK7V0;IfKYX4^g5LLG0;KwXN_Lf181rTAMe9Gpp+I(p;oNtCn+Y%>o0B-H5kmV-oFYg1~`4;aHKDdNBjbeeHCY!ncu%36bNl|wY9#m{c}05Y(pwDJo1CJC}rG1fv%F!8QYt4SU&RhU$_4c1h+3N'
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


def _bank_inner_agent(obs, config=None):
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


# Intraday banking experiment. Productive operations and resource pickups are
# hard constraints: only PASS or movement may be replaced by a short shed trip.
_BANK_VALUE = 2000.0
_BANK_MAX_DISTANCE = 1
_BANK_MIN_PRICE_RATIO = 0.25
_BANK_START = 120
_BANK_STOP = 680
_BANK_ITEMS = ("MELON", "STRAWBERRY", "MILK", "WOOL")
_BANK_BASE = {"MELON": 250, "STRAWBERRY": 120, "MILK": 160, "WOOL": 200}
_BANK_SAFE = {"PASS", "NORTH", "SOUTH", "EAST", "WEST"}


def _bank_access(size):
    half = size // 2
    return {(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)}


def _bank_move(position, target, tiles):
    x, y = position
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


def _bank_value(inventory, prices):
    return sum(
        max(0, int(inventory.get(item, 0) or 0)) * float(prices.get(item, _BANK_BASE[item]) or 0)
        for item in _BANK_ITEMS
    )


def _bank_add_sales(action, pending, obs, step):
    if not pending:
        return action
    market = [list(order) for order in (action.get("market") or [])]
    prices = ((obs.get("market") or {}).get("prices") or {})
    locations = {}
    for index, order in enumerate(market):
        if len(order) >= 3 and order[0] == "SELL":
            locations[order[1]] = index
    for item in _BANK_ITEMS:
        quantity = max(0, int(pending.get(item, 0) or 0))
        ratio = float(prices.get(item, 0) or 0) / _BANK_BASE[item]
        if quantity <= 0 or ratio < _BANK_MIN_PRICE_RATIO:
            continue
        if item in locations:
            market[locations[item]][2] = max(0, int(market[locations[item]][2] or 0)) + quantity
        elif len(market) < 10:
            locations[item] = len(market)
            market.append(["SELL", item, quantity])

    def promoted(order):
        return len(order) >= 3 and order[0] == "SELL" and order[1] in _BANK_ITEMS

    premium = [order for order in market if promoted(order)]
    premium.sort(key=lambda order: -_sell_priority(order, obs, step))
    rest = [order for order in market if not promoted(order)]
    action["market"] = (premium + rest)[:10]
    return action


def agent(obs, config=None):
    action = _bank_inner_agent(obs, config)
    try:
        step = int(obs.get("step", 0) or 0)
        if not (_BANK_START <= step < _BANK_STOP):
            return action
        player = int(obs.get("player", 0) or 0)
        farm = (obs.get("farms") or [])[player]
        tiles = farm.get("tiles") or []
        positions = [farm.get("farmer", [0, 0]), *(farm.get("hands") or [])]
        inventories = list((obs.get("private") or {}).get("inventories") or [])
        inventories.extend({} for _ in range(len(positions) - len(inventories)))
        unit_actions = [list(action.get("farmer") or ["PASS"])]
        unit_actions.extend(list(order or ["PASS"]) for order in (action.get("hands") or []))
        unit_actions.extend(["PASS"] for _ in range(len(positions) - len(unit_actions)))
        access = _bank_access(len(tiles))
        prices = ((obs.get("market") or {}).get("prices") or {})
        pending = {}

        for index, (raw_position, inventory) in enumerate(zip(positions, inventories)):
            position = tuple(raw_position)
            inventory = inventory or {}
            op = unit_actions[index][0] if unit_actions[index] else "PASS"
            value = _bank_value(inventory, prices)
            # Credit ordinary tape DROP operations too: selling the newly
            # deposited premium batch immediately is part of the experiment.
            if op == "DROP" and position in access:
                for item in _BANK_ITEMS:
                    pending[item] = pending.get(item, 0) + max(0, int(inventory.get(item, 0) or 0))
                continue
            if value < _BANK_VALUE or op not in _BANK_SAFE:
                continue
            distance, target = min(
                ((abs(position[0] - q[0]) + abs(position[1] - q[1]), q) for q in access),
                key=lambda row: (row[0], row[1][1], row[1][0]),
            )
            if distance == 0:
                unit_actions[index] = ["DROP"]
                for item in _BANK_ITEMS:
                    pending[item] = pending.get(item, 0) + max(0, int(inventory.get(item, 0) or 0))
            elif distance <= _BANK_MAX_DISTANCE:
                unit_actions[index] = _bank_move(position, target, tiles)

        action["farmer"] = unit_actions[0]
        action["hands"] = unit_actions[1:len(positions)]
        return _bank_add_sales(action, pending, obs, step)
    except Exception:
        return action
