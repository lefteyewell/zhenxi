# PhotoManager - 照片管理系统
# Copyright (C) 2026 蒙汗药
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""繁简归一化（0.5.60）：自实现字符级变体表 + 地区词汇短语表，替代 zhconv（GPLv2+）。

数据来源：
- 字符映射：Unicode Unihan 数据库（Unicode License）+ 少量人工补充对
- 短语表：人工整理的地区词汇（简→繁 TW/HK 变体，语言知识，非复制 GPL 数据）
生成脚本 tools/gen_zhvar.py 可复现。

设计定位：**搜索归一化**，不是显示转换——
- 繁→简：字符级全表（2831 对）
- 简→繁：一简对多繁**全展开**（如 发→發/髮、台→臺/檯/颱）——
  zhconv 对单个字符串只给一个最可能字形，搜索 OR 匹配会漏；
  本模块对查询做笛卡尔展开（封顶 6 组，主序优先）
- 地区词汇短语：软件→軟體/軟件、网络→網路 等（171 条）——
  zhconv 短语级转换的对应能力，此处以"变体全展开"方式实现（召回更高）；
  繁体查询同样互通（軟件→软件/軟體）
- CJK 标点剥离：查询侧附加变体（原文变体仍在，纯增益），
  便于匹配 OCR 文本中夹带的全角标点
- 已知限制：短语表为人工精选，未覆盖全部地区词汇；
  显示转换请使用 OpenCC（Apache-2.0）

公开 API：
- to_simp(text) -> str            繁→简（短语感知，用于路径/关键词匹配）
- trad_variants(text, cap) -> list[str]   简→繁组合（主序优先，封顶）
- variants(text) -> list[str]      [原文, 简体, 短语变体, 繁体组合...] 去重保序
"""

from __future__ import annotations

import base64
import itertools
import zlib

_CAP = 6
_MAX_PHRASE_LEN = 4

# 繁→简映射对串（每 2 字符一对，按繁体码位排序；zlib+b85 压缩）
_PAIRS = zlib.decompress(base64.b85decode(
    "c-kG82h#F73`Mt2@4fe410*2{5Ykx87g@Tyc>doE<1w-<9ZR+&|8=du?%=QM{&mZL-S=PT``5ovCHb4o{wA%zMd5E|{Vm#m^ZnnZ"
    "{kJat9nHVP<nOxpyWIY+?%%odcYUe;;xCN<LL<$FY37*bP5fGE?UOd%X?>bDg0wzM8(~`irj1`(57S1Hww`J0o=&&vw2@A2IlR(E"
    "CS9D<Wt6U(>9L%ia_O;)UpqZM(_@mJ=IQC3p4RE<lUkY7DyDV<C!an)sk2X?aq28nCkuC$Iup2u)T`oarv5thcd37(?>qe_^mWo8"
    "mwumVuu6kj8kf`Pmc|wG^J)D0r<0V_@|Y&0H0-8{{<}|q+4QH|9J^uq8>Er$Z_;Fw{*Gz1rA#J`j+7~-zbj=b>F-9FY8v(_Q%`+^"
    "GTk)1Q|6XNC(1Z~-3n!^X|$$n_pcLE)=QH!WnXD>qHLT-2IU%moe$-@YH3q$ltyRDP10yZxhWmWl-rT{rraZq_ms0Jd#9Y6MjOg`"
    "X*8$Yi!uS_K52BITtb<I@;S<elrN@Xk@D3vK2lyU>O%Qp8kQ)(`sXpP7pvtL%4+>@8h)sdNkfAQ*}rZ;g<P84sZdCR9~CNTa-~8w"
    "{XMAAq1>4YgY<Wz!Z1y={)Ft93VLZ;(@3KU6&%W4sPIXDder~x>bV+Ew;|<@REW~wg^CR-cB$B-!jFn$Dvqdlrc#lL*VI2ysYay+"
    "l??jks9d3PhRRJUg;ZWpc~0dgl`X0qsdA%=L6r?v3siYfwM>;MRqIr&Q?*5vFIC4>xl?scl^Io+R6SDFq-uw%9#u0`eNkmjwLDdN"
    "R4Y^UOtmUiCRD3YC8k<~DnF_<soJGl`>%hbT9>Lhs?GieRjOyH=1_e|wF}j!RNGR0PW3v~my%yleML2w>N~3asD7pTjOtIS?Wpel"
    "uk)hXlj=UzmQ)X^k)g(e8YgO4>RG17lNu&9wJ@OOfSPS;hSc<^HKkUQS{rH&sr8^%gIW%?s?^d$dur#YouhVv+F5GrZ9k_@k9r5{"
    "xYY5e^QLZxx;g3$sTWaqO8qT$Cp0KfcT9sBb@nuDV{Fo}PaTVfE9!S?xc<MtqrsL&t-sNVMl%{5XmldyN+Ton&osKH-vNy@@Q_9h"
    "_182mQFl(`G7axEuF+sg;}&(sG@em+LE|e8b~Jude?XHGwZAlJ(kP}$pN1Aq2GkwWWJJR=O~zy|X|kZfoF-T5k7;7kU_%p)<kQ5a"
    "wx0E(exD{jb$c|4Y3R{3tFmvJYT<;Yv%gV|rc3HAX}Y0)kETcJ>;8%QLz-GNc4?}ar!@6w^r5LwoeNFB6!&SCq28QkW$NgDgZc}a"
    "=_$IM($J*YiMk`2U8pyunMs{4&Ghx+)6At&LNhP*k2HJJ<UsQb4Iebm()dR69L@GLFH$K>^9ptQG_TUorg=l^ZJKv!@}#*z^CvCJ"
    "G=I^ePV<-+O`3bO=+XQ^i#{z%v>4Gmp~ZyeJ6gSHZP6;E<&xH0T0LlOqg<x-N9p~%DbjLAn;NaIv>DOLqm5S65{qm-`c$<eZM5-#"
    "wl!LgX<L`ZfVOQ~IkfH3dP3W=dgo}nqveXW2U<^Q`yyM*zqIMnPFudwZb8cp?M&JXY3I^%O}jU(EZT*%o6;_!)rt0HTFz--r`418"
    "eQMQdKcQ8R_ETDXX+NV?iS{d6wrRhnRe|;!S`}%p{Vr&K{kOWkL0he3(cYweK>IiCBij44kIDMcVMB*C9d>GWqJzGl^|hJM;Y-I3"
    "9dmR%)A2~hD;=|RH0Th}@lMCl|Luj2CLQZ^jOhHO(~?dlI=N}Qp>vbYV>+Mc=+k9RmnU7bbScpFM5i)cA9N{_ai)tyhDE0v8TOw}"
    "w-J$HkP*|VLboxU47$DObfsHJ7msc~y1I1F{L{bZ$#~GcLYETV>vVn5y+M~U-KTVW(tS&}9^DUg|Il3<8PMIPt4DXAu5WtO|K<mJ"
    "X#EO3ZuFSa!>7lI9zS{*WSV5&$l8&$B<n=ximWr4S+cHVZppe)X-d|eOdUGwZ+Rl?MdpUAH<?Sa%Vd|xuB3jS>^fN?*-f&(WVgtQ"
    "$o`P+(X&L)8a<n2`}FM7Gf&S2J*)KG(Q`}B13h!}ywLMR&pSO=<ZP)_A=e{kLhhTKIk_>pTk@LZ<;fe9GbV3G?vcDZIWfID<jm-m"
    "{H>4l&eCg1?*e%bdY8!=(R)Cz8NKzC9KAQ>9_X#-?&*Cdw?OX;xp{h<<mtZlIHk8wuL->aa<qkro<DlW<hb;ylk=lbkK7Y|2J|V?"
    "$EJ@(`tbTi@^9qp^1vm(L;joo6%rZJH{Lf-ew)7izio@YWAY>VPRI}GyC#1@-#z(R`s%qReedKy>HF2S2YrL|TOnPCls6RIDCkp|"
    "{dbdxIcn`FEKuu8VTD>J3R@IJ6wau1p>RnplfpFxQwsIXpQCU~L6^cE1#1fT^!-t&CmN)Sji5uJORXYBJ&L*%xun1H(TjAQ5Pc{L"
    "C@%f`V(OYF(pOxAboCOqD6%M?{`>C4D~gw-w|%@OT`<HaiXDnClr*T*qNGbnfs$3K@sbTCL((O|p-IV$k}M_KV5qVsmF=nQQ8J;*"
    "6;<w}ax0ZHRqmxS`tKX#kIHZL{jBm&m5o&1QQ27K^~6vW=3IHI!b0Wms&G-cn<{uJQ&NSG$_A>C&@WNNg4&E#v92;%RcxxlMinP2"
    "e^JGm%0E<bt+Ku<?p5AW#lt@fMMGr@s(4eGoGO|!?W&@ya$56EK}i*ZzoVf_Ir^PdsiyKbRcihn9;(z)nT0BKsjT}wRXC~ANELNo"
    "dofk%pb7_7x~ZI{N~X%>RmmY!+j-Nkq{?NLbyc}a!9bN8D)Uq2rYh_HN_taOUaL%`%6nDrs`BCQ5UcX}?=Vv3i^_gg*-`ncD!)~^"
    "r^+9d$*8iga(7h@=+{<d9j>z~>mYPhC8M%+RVk}VNmT}_qWc?a8>(_vm9eT^RpqWKwyI2&4r#?w6-QOts`6HqkE+*IZLS(u)m*AZ"
    "q8e+}yhx>~nm1K7RMVm6N44^*dQ+`}s%=%P^mlHn)>t(bsx?)Oy=v*{In~<guZ(JERDG}7GgZB-_FOf0s%@&qQFXMzwd#yix2!s2"
    ")!eJjOSKc#d8^t^b-SwNsjfB{sjgPbsjj6OGu3rfZKJwcXRW${s!dckRINbuDyq3sy|!wcRIj6YUDfNW#zys)e`noatHw_CG?=e?"
    "M^(S5-c8kJs^_Sx9(7gwr+T4kXbXD1OV#_S=2rEys(w`cf@-;{Usm<2>er|os(xKH^l1O@yjJ~zsuxv%rkbYeZ&c%;`p3WXT=nm&"
    "u177^t*E}O>Sxt|s!mq*9o71%zNf0%+DG+tKTzG0>T9zr)sIxqSN-_!Y^#2vs<s*wRJW)GCDnVWL0i>#YM?!y)L^7~1vQwePDTyp"
    "su!riLUnYzR9!9CYCSdBtHxXn4ys#I14DJR9i4($4aedg)o?=XsT#i2u%U*&8ro`<Q^UC$<&`y6qmmk4)o7?jeKoqPk?w!g=%GeY"
    "8no0jr^atJt*U8VO_ypCsaZu$hiaxJBQ=|-v9D%39v0Q?re--cFR1B2%}dlOsd-sVrfRM=`)c0Sb&;CuDQ7j`D1G+l7d461{H~@w"
    "HTTo+NiFheG*gSS=)Jvsrv5^$UusiS+n-vN)NY_Q8MT|J)miP9YPnUrwOT#Y&QbfU+7~FwtNlo=E^0qktG(K<)uyiY+rLLk?ayjc"
    "QF}*iMr!|7yF?w@YP(Sf=kL*0$C_GR)UmHtH+8(I?M@vZsXtT4ms(}j$xzFyI+>#P?a5K6qB{N5_MpynwJNA{Q>_ejKB(PKozLp9"
    "QRj;~WYyVJ2UDG0wY{kGTj^5d9I3-nU9xI>RTusC?5Imotyb#NSI0<QrfO4Gmz7%W)MfYgIH=2BZ9Ymrt{<MdXgh|w_-dj1U$yC~"
    "OQ5zVb@{2oO<gN$yH(e^+8)()trmg0?v%c}t~Yftl#x}&RT)*aj+HS`+r2UtYI|13TAgRg*r|O+8GCiHlwqn}q;&Ptww2*3z2^;I"
    "tvAXDmEPyKyjm~Rt*@?Mb(^VEMcw9VQ&qR6I;_=grLK{>>6o|FO=CRO?X1olb-SodL){FuI;xvS)$LuK%Ifx%$w=K?wW+C_uTI)d"
    "s4h=+*SC6G-E~It>fTm|gSz+BCQ<j1Iu+D?rS>^>kI_4+M@QYy>akY$gL-V$eWxA{Ia&4i{M&oF{)v0)@l$42nG<E!mAO)8Pnid0"
    "mX&$=dz#9;DRZVw-RUdSQs!2f_TTfWOh-K;Wd>@QQD#VcSDDej*2*X=tE`eTJ!Sor^-^|@t0!ewl(kiML)m3z@0C4J_D$J4W#5&3"
    "Rko{aM?C{7xytD&XRCD4QgW1=rP51zZ}t4Dm;U9|yR6(q>6)ZmRiBx14fQ!Hzo9;ca!%^=QhrT+-s-(lpFq8e%AczDUg^hOxvl)2"
    "axTh0srOd-clD|(KT)r)`s#a3w=4CksP9?58|tgyl?N46lyg<Vh{`1uES0lX!A<#EVyahF1+IGUR9H~XS%pQ;K2+FH?}G|k(mbm0"
    "t{g*!mI_xYbd*0<;fI=f)K{;b3Pbhks4!9COocxcZdH_3{y;@F6_k}e;LbrsJN2xpXs_OD72TEJRFR|J7Ztsf{uW2R@;fT}saHwG"
    "S?roB?kYD@@j!W5rRx(-9?$-~x{Bv2Ua0t>-X|4X>NQZYt%AIYKPnun_@~|*m1NZWs*;j=l~qz!@1;sQ$|<Nszh%xU*(krOl7n(%"
    "m7G*)sN|~Lw@P#znksp!PevulpSw}Nta{bdFRxyG^(*|jTlE{N?@#?E%3Z17Oa)o>oB#W={}$>sRKK-)wbW0u&DHPx=ML2GroyB8"
    "*(z?T-&2Jb^$S!`RKG~Mfzl;Scwk+eBy-jUQn+JX@c1pxl>eL`XR68#Ia60o<zMTMIMY_IHfOY>9%nRz&l#P^BWKnsE^}t1;u2?c"
    "SUk?0mHXk0cGu;M{pZHI)%6}{92M6&lc;3D*}QW0oGqwu!`ZI#dYm1qsL$Dn3a^}9a<<Lc?Vmg3>|T8n&gyiZIIFkEnzJ!y6V3&x"
    "A8@{%ejA+kIG^XjR*g4Yta2{mVvlnRE>1bW=HgBoLoOb<pxZ0wPh7lnF2lv=-#g|~k&7OedeS^|Y0SALm!6z|aLK{0#U<@1=5m(v"
    "7cN&gYjL^9`7@Wb<r|k5To`eAEuABmHQtZQ56;iIta+|ne*eAST#h(@=W@b@30In&&vK>1xhhxYoX>IPkp{Z&{98*!|2|wv$R2RD"
    "q+hRGop80u)tIX<u8pL5;@XaDHLjhx8gM<swKvzlTz_yq=6Z!2Q?A?GcysN`jgadOH?v&xxmn=)lbc1Zo7`;aw<k9*T)%VE;JU@l"
    "8#nUYG`YUyrp@&gH=ln&lbepTKHPk9qs7e+*L2^fV$98en-6Y=+|bq{*0F76xUuDS!Y!LS0k=Ec`ElFfZk<~ucYEBLad*$14tEdS"
    "eRKCJtuJ>CZq2#taO=svDtFr4+j6JHy*;<O+&gji!@V1~ZSGlr`daAO+_Jd$;?|UVK6icY#oP+GU*k^1{WiC|+#hhS#r+xgdpu}x"
    "-{QfL`z8-|X>jJj{$D#>rookmJ7o=dc;i9HL%lz9JbY8!=TVu59*=6&-tc(J<0_969(g>;@p#0OI*%-#G<me;NuS3CPgXn`^JL2-"
    "lP6~$t$Ct5C7w7udhjIR$%H52zjm7A(U_+t9$$D`=JAcERh|@iI^ofVr+T8n(;bg{JU#Ge#M2{>%RJRK?>xQobj4HM+4EGJ{qa<L"
    "NqB1WxWdyXPqa0Mr@D<u$6+?(nQm<!J$dHy%;8zUvnS6NJRkFX#q&1Lw`9jW-}Ai7^8?Q(JU>%&$8$rPTV5P_apFaiMq^&KX>Rj!"
    "!OJW!SG?@-YQl>quNG-`#H$srdc4v*xx}kCuXG#nvdinTzMXj8=f$1ZGhSVJZSnfX+q_yldAs0kmbVAqj(B_F&6u|qZ)Uu^@^;9("
    "2X8XG^Lex2UBFwDcM)&0yo=M^i}zjLPI*7$&4~9K-fGF7cMIO1c{k_1_VVU^%-b>VlQduCLxHz5K9qR-;X{kJ89q#T*W|;A*FQcO"
    "yb1Vl<4wW`jjG!xZ$du)_*CFilaD^1T70zlG~{E8Pg_3b`E;UW%O`_RMLwB)i1=jlamS}8A3uEh@j1`u3O^&h6#3HPONGxRzO++)"
    "L0#5-%J9YHbCWMmKHGfFi2dPfIW4aF+ThEcuT4H%d~IPj;_HUb317E-?ecZU=a{cozPNn7{X3!82VY8TT-jK%VJI(R!{qCS4U3H~"
    "8!t9mY`occuo19v<XeG_1>cHnH2GF$<HR?8v%UFNV<XQugKs0g>Ax#}l=wd2N0aY$ew_I}<cF7*9X9KH57=z;W64%VYB{zFqVEu^"
    "%8xEvbvDmz>4_0r2fl0hl^=7qTz<^h&aio6yUA9c?G>8_+gmm>Z136XvVCLo#`c#V3)Y+Sk+7YRKjEh~V)C=Wk1sz5Y4yO*DVu$M"
    "YO@wU7i?bmx#nk<pBuhM{5<@d`@Hg9x7x*spLe#N{509T^3$PCmYo+n2X>e2X4ze_W3YQ>$7I*0`Ho$O9X;gn(_{C|&Vt=92Wxf{"
    "4mRv%I561Daj<8vz`=>VA_qJ6N*rw2D|2vUufoBFy($Mc_Uasb*=us(ve)4tX0Ojd!rp)bi@hNSHhUuuBKF1{JlUIYV6r#mz-Mp9"
    "`quL19DLYYaPVMn$$`h-mV<!3d)m-)o5K=&PY!eJIUHu$b6MY+-iw2fy)TDN_5uzwthYy4XYa>hhhG^E8~n;~Sm9TJ!vepGY2(YU"
    "5{ET@wKyE}tHWWRUqcR;{F<}=3cr>d4*0d=aK*1JhYNn~IGpk8#Nm`*7Y=*;(mW%6X`VH|^w&+#)jV^4z5lnPd3OBHa@gf}p2ID_"
    "wZ{#=D;!?<UFC4k?*{Ao<lW}*$nQ?ti1^*-u+8rUhq}MwsLAgQhd+L6?>@ix9ESY9aiAr44&VHKaOm;d;_%CF&6Du^$$`Ufhhyzm"
    "^L+U2ag^crD{aL5_BqhAG+V%L9V?UHA%|KXb7=EB;qb<99k&;MbgUfylsU@sr^eoyKXnc*{&fHGe0m%j{L!>`{tP&L@@LFZo<9?g"
    "3jCR}{?>eE9Ci4!<fzIYy_Ob#HXIH3vt@nXe)b$q_;cc@!Ji99BmP`jS4W>aM@9Zv9B9i=j=KDDII8f+<51gwbJXU~m!mR&LeWLY"
    "C*r8aenmPb_NyFC*{^Z5W53Q(kA0olD*IiI_UsS;*VLRV_U9bUSf?ynu&>$H?5{bRv%ja-kNxw%J>cIsTC)G(Xv@CI(UpB2+ZX$q"
    "=ghvFHhlIy4i4<UIMVuWetp>ga5Q9J6CT-*RVHL#NA=3z{J&g$iyYnfTjI#zZ;vC3zdCwl{%SUpzdB+M{_0&f<nQ+14*Bjls`K~C"
    "q03)`!wG+HtgF`VLmFrPYATz*7Dsy2=E&i%%aO-lKh;IiS7*7!Uwsy|X3Wunb&(l8`TI+o`e>K2+jCIi=*~fnb+r)a-S}W#6nQ%M"
    "ZH_h^^f|h4Fi^Te3r7D|8tDA$<F?>PFG0T<UmWMt{)OWTE$19JIL>k0`oC{;JmdHULrXp!?>H%PJm#dtx_(Y7oMbtvOHFr<oUA#y"
    "u>RI0*YsQE<SnI;f4%g(;oqHqGyZ+~H{oB*zo}&Ik~vGpl*~@DBU<bwyTUk>tR>ljWNpbBl67dWJFaAW$-X3emF!!xImvz`+mP&6"
    "vQ5dx)VWJGk!)RZMaku*P?UUD3Kc0-r7)NLO$z$=l)_i?87a0Tmq>9W`HK{{Qg}=8B!#XNZ<6~-(UrnXioWDFQp!s)mQp?K{iHOM"
    ";zUX_$sMG$O4~~*Z6vQ3c$H!(rC9PMDJ4>9O6ezszLd*p$B?oH@TJ_8LPyGNDRrehkz!5CGs)}GwG`S?-bi5}<(-rlQof|VC*^?J"
    "wp7Zg-;zp&ik?)esh>!trp9NfPNnjc>Om@dsh*@_OZ6s|P^wy}`yZ*gQVXfll=@lfEonGZ{7SPX&62cg6cnU2l158fJ890OrFH7k"
    "wy4>XPFd;=>C~k4l+Hc%%hK_rxs=XJTAp;P)P74>zdjz))rD3@x(8{R(mhGNEL}^QmUKVTJV>uEtw?$UX}Qu{NvkNmNa{`LXQXLJ"
    "zs~cK^i63w(zm3ZmA>~+zaL9;A%g+^Ygf{1$Y3wMx(treeahe@jjjwH(!9wqE6s}xOVTULP`|rZGSpOe8TO^-%Wx<y-A<%Am*Gx&"
    "RT*A&l_*0)Y6}@Yq;r<xNBVmiWn^f}s3Og^jB3)?Z9{5f8FlHrkkLQ}9~o&oQyHzL^_I~|njINkrE`&yoA!q?^8N*R^h*1E83oeZ"
    "$hb<GwT$&*monCDR~av*8p!zgFFs>KMy8A(X@4YRPlle1-%_v0_$z}*#(@k1nPj9hlSx5_j!a5YJIO@nr7e@%KmAEv>R*}6WZaj@"
    "N(Q>G-;8?nK}B08f%G>r`AKIf(~=BwG9A*PAk(=_XEI&Lv@O#$wLdaFr-ANUGQG<@koi;Qp)7{7D9P+D%c0CNvRrdR_fIlSWa-Od"
    "EUSXdU0JPUmXp;^ItN*q>3AfoP?nLbezMBQTI<-duE???>z1r8vfj(ol(jZhm9-^vN7jx^Z?b;Nye;ccW?9)}WtNvsQI=)dlw|so"
    "O;eUF*>q&?$)+pIL^f+#Y-O{Txt43QZP{q-nrz-O8_Fh>xhdO{eg(+3CWEeQ`)Xmyc1WFuZ1suT%63kA|7@33a%B6ZwjsNfY)#qM"
    "WLK1Z8|8-V7qUIdekpq`+5Rtysq&UXnGQ`k=)V;?Ok`J*gCqNc99-G&<lxI;E{8A;UUDqU{wT+W9F}ry%g&PHNOlD|YMXmGZe(AQ"
    "qn_x=Q3EXGcu%K&-KwsZYv8*a9oaqPs1=5CD*f|&s>?Ymr<R=aa%#)DAg8{Zi*g#txg@8FoXc|B%DFD5qnx$=NzN@f8EN3i=`QD*"
    "oGdxF<>bh@Bd3p?yK)NTT$NKS=Zc(ua&E{uBj=o)Jvp!B{Fbwx;>-CYm#ml@x#Yy$$t5r5UM>|ew{oe8Y00G_=2<Q+F)woIh^h5^"
    "Vm{^47xN*Pp_qnTMq=LNG8XeLmx-9RT;^ha<+2p>Etj>Jkz97E{t8_7q6_uQQOu8Au40CAF~t1I<soJwm#3J%Ts*O=a(RoDmrEd4"
    "O)jBwFLKR_m6K~pth!t^&r7Zyu_|)yiPe+qK&-Z0hoYYV*O6EqxsJsu%XK1FORjUVigI0v)s*XodRlWU)>W=Mv37FRRC~Fe#2U)="
    "D%M!^i^e+3^)A+0t`D)cay7-;$ki5WBG;!_OSw8?9p&nZb&~5#tc6@7v8HnUi8T_VAl5*PqF8e=G;?1Jy~lhp8uS~B(G>F_MprCX"
    "49))*LzAz>(6mo6W@4FQXxfJu8?k0$Xxf_?n)5EkK`cv*qgb{Wn)xNhMJz`QLo82>`~R&ic2*2cn27NfyDY|6tXPal?3x%l)Y|4x"
    "?7ZA^Vi)9A5W6I|ve*^5RmJ+rtuEF_ZcVWca%+qAm7AuG<kl0rC^wz)KyG8Pb8?%Dosru@?55n7Vz1=35_>5(9oviC4q^}Fb`pCo"
    "x3kzCx!uHW%k3fdP;RE!6S?WUyK-~Ip2|(rHstmZGnSh#mM^zJ?3vs&`ABYwSb^O2E4427tk^xdYyQ663u4sduA|+Mdrj<?+*@KV"
    "<lYhcEcb!fUAd3M-pXAwALKq2`y}_7*hjhRz3Rwalkeod5qmH9?f>mX?6urAts(cj*mt>W=9}DIF+I6|#lFZr5&J3+9kHxDv`0rC"
    "Z84AX(7sH0=xmncp?z8M(7qn>&{2BIL)(1G!xF124_i#F>51*h<D+T^dFWLe@`%!TUmiMTRe2=;{F)iDLNSYCSH-MRTOTxi5cJ_{"
    "qziqNT9|Ld)Y;L;P@hdL8H%lqYm&E^+OHnfd2!`gAtxu#mVRH$vy=L^=r?J@kmp;TrZ|0W+{Brt%c(d^@s{GO#9N887H=cYM!dB+"
    "Tk&?{?8MuOa~4nQU&K3$a~1C@jv<~Q&P_Z^oV$2?aV+t)Wm`N~97kRmaa{3iaXj%};=IMXi}OjpTH=fM5hoDuElw!jSDZ*ZPn=l1"
    "P@JE5zPK6j0&%nAIpXHzl@m8FudKKQ@qXeK<y927EU$vN74Z^rYvM)XcI8zOw<oWfxP8*MjXRWAS=_0-dg9LHRTXz3ua3AYd9}se"
    "$ZH_(R$hH^^-2%o?x{Hv_aNR=+>^ZO;-2L-6j!hJBJNFIO>y;lPvSo0)ezTCSK68<FForeud%p+yk_Et@|udP*YyxLme*X|L|zN="
    "G{0V^=AVeC`E|f6^3nmX$xEl8E-#&qro43U+w#&#9eI_+>&q)I-auYm@ka7$i8uaVb1tvFc#D6due-bqdF%DQ<*nEIlJ`a4b$L7T"
    "e#&PnzpwZm`Mg9IsD4ep4fz!0JCu(v-@SZ$@;!)e$TyJBM}nMu-V#*h?MqM-zac?g^g}Ob$|o;DD_!p-=!$Pi(38(fg1-2735KHc"
    "8_eYMm0&C1t^`N<{v<d_u#mtIU9p522`mX~5}zcjOMI5FA@N1RCY9zAb|p3>>`8o;a3Jwb!nwo`3D*+qSqF(f65b^CC3GZyO6W`M"
    "N%)ocC1D_OAYmx6BVi=*Tf#)*NTR$Xd5MaW<RmIfl9i|;Nk*co#IZ!0B$22mNkO8%YG}zolA=UIi9?Czl9VJ`NYavMDM?kLmFVYE"
    "w3ehP(NU6`L?=ng5?v*!NMuNCN_3Z`A(16XS0Y!EwnV-peThOzIub>a^dw3o8B6q&N=f3(KS`WZ`r8*5BpFGpX*EDel8MBc^Dc2y"
    "lBvWkiGLDn!kNT6Cbq;|Npzrg66+x7_-J=0s%glFB)T;vxk;i)G@e7Hh5S64uaFta&qZb`zbP_%`DuwGzd5os<@?YNv0n$-mi)@l"
    "Pq`#PR_ia3og#Zgc7aR{`mLAgA-j>^0@*7vIb^kkHT28wmqpe`riyHU>=;?S-Wa*8{3^&5<TpXCEWayqHA%k6wUG&t>mYMNevNz^"
    "`4@5~3MJ(GC{)w$7KI*iUlaz&-BB1Je@5YqoF083-$lVjE=0jW-bcYhE<oXpd<TU9xh0Ba6muw6kUya`LUD=GBK5l{t^V(?rPoI3"
    "MvV}qJBm+~o+zGB&Y<{1IV;;D%6SwMl#3|FDA!T0q1>U?1mzxjdbE#T3FQHLWt4~LHBcU-r*$UiRZ*Uzr>88@tDw9`uaEKpy$;G}"
    "XustvdOeh1=#5eSpw~qCi{23B0KFE<NqP)W$)IPUl11-^N*=ulDh2c&s8rCKp;AR}gGv*<B`PiSuBdd-JD}1<Z;y&5?4qLCR;Xw;"
    "6O|QuXH+!F6qO@-cT`U3%~8=j1}Y}{4ODFOE2y~Wy;1Sd&!eK*JXC!2zNmcBZ=#|JZB%0Pd{h$jGpPK~`=P376I6@nEl{nXUqiKu"
    "eihX^`ejs`=+{y0qMt)m^L$X%v2szJp<hCEj(!nUO&FlML+^#^;opj?n$SV@g5LwxJ9-hS5A<SG-{`kd_0hLc4bbnQ8lrzk^@qNJ"
    "S_b_$YI*cs)QadYP}AOLsA=ze)cWXOP#dAYLv4co12xTXLrpWBpr4uB0csocyQuBa|Dbk6|B2cO{WWSA^k1l5(LbVQpg%<IhQ5W`"
    "9sLe!PxM!)xftmF2ZIc1Ukoa!g&1gS5e8M%v*<5T&tuR-y@){r^)h-})Enp@P;a9@M!knY9rY>tA?iyEYN)R<=%cQACa51UD4>4C"
    "AdmV9g8}Ln49ci$Dy^fb0@NS>80tEwBh)PnN~qfy<WSdyG3sv&nyC92Sg1$n?a;_#utK9i@eqv?1|u}e7~IgPU~ol4Qw`AQU~oi3"
    "vuT|n25U4X7#z@;V(>&m$IwJ$j=>xaO?yXUgTVuhEd~oTbWXL7rahsdX=i9$G1#DS!(fYsiGgO&oKrNM{~2@)Z8YApy`Z799HE)P"
    "V2P&Yyr8M0XP{X^Z-A!e^w89tE}C@=ifA@5%%C~I;De^l?-tD&dLuM7TZpEniqX_D^wHEYbkNi!6EyD_e9_cVO3-{^V4|s`^hPtl"
    "V2oyh-uhoV2++!5m_@6A!4Iu6hDEe$7<SPbU^ql;gn=HNU|2<Kj$s9@ErxltbObJF?M3gL)(OKlT4(e(Xz8q7(K0ZI(7I#TLCeIj"
    "jFydI4=o47I$AD<O|)JZ_R)IdH$cnBuz}VO!xq|k3|DBE)wr%(4A*Gu)0d##z_5h2j>Z)24u%`FyBIFf9;5$5Tj%bD_5#B(+Di;4"
    "Xs<AwqrFDoL0dB~(B5G<Li>PW4sD$XZBtXt(0-wRM*D-|0qrk_2HHV-jM0w&?e>m7cT;rqsrS&)e)s6~(Ep;-$MA%Xj?xyL$-j7Z"
    "rWoGP(cX9HY%si_b4*V~bo4%Hp>xKdjm`zb0y?*U>+R^s*yvd4DUXhhjD?Pl%mW?GlSSu^p^1*(EqboL6XxjX_&m`qpzotw`FDqO"
    "b*Ap<>c|Yx)t82cuI6#j)%*F3u8x3~=(ArycaNcq?h(Tyx(^KXsEwZPKQVlvtG&O`)e)$nt0QnlSD)@Zy82cO(M?b@(fv_bUyRxG"
    "q&I5rUmk~A|A$cq;|oSPjIS8wF*YzNVSK}=g7F=rD#j0t>J()#YGC}vsD-hMQ5$0$qb|k{MtzJuj0PCLFq&ZOW3<I2htVFBEJg?F"
    "R4_VXqAgr74luf69Ak9DB#+S@lM+S`j1!EWm=rN`{%_xy)G+#DQpG65q=iw0NgJaWlO{$9Cfeo?6OEL|q=#`yEq@qm<|oEAOf*a#"
    "lOe_pOf+N@lQPB~OvV`ZFwu~jS?dol8DTucWQwuwSQsy;=wiIWWQOqu6RoD#(!qEq$r|GWCUcCB7;6}VmN`r(m{u`eVmicBulI$i"
    "jfsb;i)jT@AJY=1n%TuntDP~^Y-`L~n7lF5Q!bdzF)d=IJ8jGiOs|+(n4U0uV%EV-n<``GW2W^(Y8#l>F^e%Di8ec*l0H`RIp%H5"
    "7fSQ!g38}wzT;Df`5v<bb0-bDn1`&-*J6jo7K=0H2^KLHS^S&gVp+iAfn|yGfn8QO`@*tH?GlzVEc;k4u$*FfO0NYhFIXP2YSZV6"
    ")sn*}Rwq8!v5K+kVV&j3#yXEx7wZz~i*a4W%EG#i^$F_+)@Q7nSYNR2V|~SXinW3D0_!{0E39u=hgiR`{*nH&Z?f3Fu*qTj#wL&L"
    "2b&_cUu;U)2H2Fb^|7g78)8$#Ho~TXT@ITTb{TBi*yXY5U{}DVi*1Ze54$WjeQbZ&jIk?YGr_Ke%>ugyHe2kf*c`CyU~|H*jm?7&"
    "9yTU+J#1|3YS=i~)v@ug8)EapZh(!CT?Lyjc71F@?7G;*|N7e!c4KTc&ji~hc1vtE)eKurwZK-BOtI}_H;4YX|C3Bq;fL)MyDheJ"
    ">^9i0_!(lm!)}f35xX6>XKWK}Z`d8My<>O8)>0EK(QGGdpV;Z(xY(_*)r4p4F4$|Q5A1aiOzgYZS=ejWPtw=s&Lv%9?cUgH3?F-q"
    "5n!+JLhMJ_Mc5Cq&tN~szJUD%`x5q3>?_#Mu%BbU!hVC}9{U}RN9^}F9<V>+c*6dQqjqiJXkdTC@rL~a$2;~GjvB_nQNwsRde}!e"
    "I@rfJKCw@5w6Xu;=;Dxvt~L(^9DN*$I7T>Bas1#=qhg3d1IHH*EgZi%v~kpuF7$1G=;4&bp^xJahapZm97Z@MI84%bs#}~gILsvH"
    ";V{RkfWrd%-af2wv~bu$-}8qH^xb%PvRlT%#qo^88>cD`ADpx#z^R3UX1?N(;MB(9hf@v5EKV9Jk5d!JB2GOVD>!v<tm34>YB*`6"
    "I!+ZF8#oPc?EZ_`QLDXi)ZxA0xWGZrUEx&6afg$JzvFtx>4ED5CzDDRPETA-oLpROoIG5$<cq6=a~4+@=MJtR&Rtw%oO`%_aUS6M"
    "!g+{mg7XAM2IncRKF)Jo-#9OEjc{J$`oVb%BZu=2Mg`{wj55wPj6BXy7$uy27%iNCFxt3eVbpQS!D!-Agwe;P0b_tm6Gji07K|<~"
    "Z5SO~Mlj~MOks?1Il!3Wa!#!RE;kq}T(p-7E+&j6F1F|w&E<`2fXfHQ3>WQjjY|S!i)%)74Sdyp7r1J_BV6+^HqaN5vBR~9s}4&I"
    "hVEz*y;x161ELxBxDH_ya2>;F;5t+J8m@ZnKU~)^4!G*+I*gj_jO!7`5!Vw8?aP3nH8p1yh9&y-cWdKT#H}X<-5I2DAGaZH4ctb!"
    ")p0XPmoaz!^+|AVN`8y`?B9)a-{IcJ{isG`+|L+)alc|x$KAxFfcq2qEbdzP#-oKt6^{uXWjtnhMtIEejPcmvnc#7OlflD+lf}b>"
    "lf&bK=MRqnP61{XP7!7vP6=iWP6K8gP8DVoP8((mP8ntgP6uWeP7`JiP90_+P7UT5KM&>%P7me+&IINX&I;xV&JgB4b=ELXa7Hi<"
    "I0KkBICGc}I9-?~oCQo5P9NqQjsa8iEMaBfoMCCI4XiSpE37J<11!yUfu+6QVGZDfu!e9fSR*(OSmS?wtvQ?zEY0A-+QNCl+QE6j"
    "I>2#Yo#D8!bToWen#Y8td2CoVoHr~TnE=)YZU$Bi=LYKsw+1^4w*or{XAC<JHwU|vYBsw9Cx%^xKIwKNb+)jZaEq|pa1z)ZxCPif"
    "xFy(qxOv!fxLMc>xINfwxLw#AxOLcjI7iq=xNX?y)Y-wlz-__4!tKC*z-_`d|DXHBzflKn1GWpd5Bmjo0{a8!1p5nT4_n9Z3p<3X"
    "X(PCE*a_SLo;kQxJd1Frcvj#J@zmraJT>7O&jH*eo+G#mJjZZXcut^m_tcS$@La=b;kkjM=kDR|@jSrY;(3OvH<*s+4^N#_z40u#"
    "8$3V%*8cS2RPfY1TewH~ddX)h-{4;1>xJL{?>q3dDVNH+_26scZ}>a7N$U0CmEd3DmEm9DRpFoD_2Ap^hVWnT=I~v3OZW~vU9p(("
    "*6^S3_V5jOC-@e;3;YK>3%(D}hW~}9y@c>SsW#$;@PF`r@MFBPsW-qY2S30o4?n`IgKq|}F1~rZdia*`>f@WmYk_YCuO+@kyf*k2"
    "@Y>>A#mm6Af!7`1HeM#a9lR`jTX;G6*6{k^+s7-xw~2Ql^+tH>b=~l;;@ic$hHnpVZNHB92;V8*6MTnw&+r}Nt?g_5BffLIulO$T"
    "Hd0T^@9@ufTha>f)?U_ld-xvk{^GmAJHU5~cZlx<?+D*LJ{f#x_+;_j;giF6g-_vMrT3|%-UOfO|E(rj;-g8<_-K+NK4bX0ox=a%"
    "qj@g)=xo06IpJ&IbHjIlk6!5&AI)&X$HljdkB{#iA5CK8qe&k4#PD_SbANitei>h#lv?U(vkiQo@Z0$6&7d=@7p2#(HMK9D#5uk$"
    "d>w6_8l7bwz!&MK?)OVQ?Lu4Dl8ARtd}E$>5R6lu&ESaOgy4$6M_{SBgTO=ZMWBn)9fBy;84TioZJ0+`K-fT7MY!VJ7vY79GlUL8"
    "1EGh7mcJ2h5q=O}5yl7;gg-=eL^(taL{&shL_;dw5qXHdh--*Di0f)pN8Co-MchODLp(r|K|Dl~MLb55gDxtPBH{&-GU7FoJmL+K"
    "65=hA0^&WD1H>mJ6~qP-ZT60&ir7J-Ex)DsK>R_{K+;5_O|_`iLDHdMg`}IlO(fdm42kwQN20x~@yn)*1Ad)U->APnem(p)_-VO|"
    "pZ_1(UDuu"
)).decode("utf-8")

# 高频一简对多繁字的主序（生成时人工指定，语言知识）
_PRIMARY = {
    "丑": "丑",
    "于": "於",
    "云": "雲",
    "伙": "伙",
    "佣": "佣",
    "借": "借",
    "克": "克",
    "准": "準",
    "出": "出",
    "划": "劃",
    "制": "制",
    "卜": "卜",
    "历": "歷",
    "发": "發",
    "只": "只",
    "台": "臺",
    "后": "後",
    "周": "周",
    "咸": "咸",
    "回": "回",
    "困": "困",
    "复": "復",
    "姜": "姜",
    "尽": "盡",
    "岳": "岳",
    "布": "布",
    "帘": "帘",
    "干": "幹",
    "征": "征",
    "御": "御",
    "志": "志",
    "才": "才",
    "折": "折",
    "旋": "旋",
    "曲": "曲",
    "松": "鬆",
    "板": "板",
    "汇": "匯",
    "沈": "沈",
    "注": "注",
    "游": "游",
    "漓": "漓",
    "熏": "熏",
    "症": "症",
    "秋": "秋",
    "系": "係",
    "致": "致",
    "表": "表",
    "谷": "谷",
    "郁": "鬱",
    "里": "裡",
    "钟": "鐘",
    "面": "麵",
    "须": "須",
}

# 地区词汇短语表：简体短语 -> 繁体变体元组（TW/HK 都收；
# 只收字符级转换无法产生的形式，避免与字符展开重复）
_PHRASES_S2T = {
    "B超": ("超音波",),
    "U盘": ("隨身碟",),
    "下划线": ("底線",),
    "主板": ("主機板",),
    "主页": ("首頁",),
    "二维码": ("二維條碼",),
    "云计算": ("雲端計算",),
    "人工智能": ("人工智慧",),
    "代码": ("程式碼",),
    "优化": ("最佳化",),
    "体检": ("健康檢查",),
    "保姆": ("保母",),
    "保存": ("儲存",),
    "保安": ("警衛",),
    "信号": ("訊號",),
    "像素": ("畫素",),
    "充值": ("加值", "儲值"),
    "充电宝": ("行動電源",),
    "光标": ("游標",),
    "光盘": ("光碟",),
    "公交车": ("公車", "巴士"),
    "养老金": ("退休金",),
    "兼容": ("相容",),
    "内存": ("記憶體",),
    "内存卡": ("記憶卡",),
    "冰箱": ("冰箱", "雪櫃"),
    "出租车": ("計程車", "的士"),
    "函数": ("函式",),
    "分区": ("分割區",),
    "分辨率": ("解析度",),
    "刷新": ("重新整理",),
    "剪切": ("剪下",),
    "剪贴板": ("剪貼簿",),
    "加粗": ("粗體",),
    "区号": ("區碼",),
    "单反": ("單眼相機",),
    "取款": ("提款",),
    "变量": ("變數",),
    "合同": ("合約",),
    "噪点": ("雜訊",),
    "回收站": ("資源回收筒",),
    "固态硬盘": ("固態硬碟",),
    "圆珠笔": ("原子筆",),
    "土豆": ("馬鈴薯",),
    "在线": ("線上",),
    "地铁": ("地鐵", "捷運"),
    "堵车": ("塞車",),
    "塑料": ("塑膠",),
    "墨盒": ("墨水匣",),
    "壁纸": ("桌布",),
    "复印": ("影印",),
    "外卖": ("外送",),
    "头疼": ("頭痛",),
    "字体": ("字型",),
    "存储": ("儲存",),
    "存储卡": ("記憶卡",),
    "客户端": ("用戶端",),
    "宽带": ("寬頻",),
    "对话框": ("對話方塊",),
    "对象": ("物件",),
    "导师": ("指導教授",),
    "小区": ("社區",),
    "居中": ("置中",),
    "屏幕": ("螢幕",),
    "工资": ("薪水", "人工"),
    "年检": ("驗車",),
    "幼儿园": ("幼稚園",),
    "应聘": ("應徵",),
    "录屏": ("螢幕錄影",),
    "循环": ("迴圈",),
    "恢复": ("復原", "還原"),
    "截图": ("擷圖", "螢幕擷取"),
    "打印": ("列印",),
    "打印机": ("印表機",),
    "打车": ("叫車",),
    "扶梯": ("電扶梯",),
    "拖车": ("拖吊車",),
    "拼车": ("共乘",),
    "掉线": ("斷線",),
    "提成": ("佣金",),
    "搜索引擎": ("搜尋引擎",),
    "摄像头": ("攝影機",),
    "摄像机": ("攝影機",),
    "撤销": ("還原",),
    "收藏夹": ("我的最愛",),
    "数据线": ("傳輸線",),
    "数码": ("數位",),
    "数组": ("陣列",),
    "文件": ("檔案",),
    "文件夹": ("資料夾",),
    "方便面": ("泡麵", "公仔麵"),
    "显卡": ("顯示卡",),
    "智能": ("智慧",),
    "智能手机": ("智慧型手機",),
    "服务器": ("伺服器",),
    "杀毒": ("防毒",),
    "柜台": ("櫃檯",),
    "标清": ("標準畫質",),
    "楼道": ("走廊",),
    "榴莲": ("榴槤",),
    "橙子": ("柳橙", "橘子"),
    "橡皮": ("橡皮擦",),
    "死机": ("當機",),
    "水印": ("浮水印",),
    "沙发": ("沙發", "梳化"),
    "注销": ("登出",),
    "激光": ("雷射",),
    "激活": ("啟用",),
    "点赞": ("按讚",),
    "牙疼": ("牙痛",),
    "班主任": ("班導師",),
    "电梯": ("電梯", "升降機"),
    "登录": ("登入",),
    "登机牌": ("登機證",),
    "相册": ("相簿",),
    "短信": ("簡訊",),
    "硒鼓": ("碳粉匣",),
    "硬件": ("硬體",),
    "硬盘": ("硬碟",),
    "磁盘": ("磁碟",),
    "移动硬盘": ("行動硬碟",),
    "程序": ("程式",),
    "空调": ("空調", "冷氣機"),
    "窗口": ("視窗",),
    "站台": ("月台",),
    "笔记本": ("筆記型電腦",),
    "简历": ("履歷",),
    "算法": ("演算法",),
    "粘贴": ("貼上",),
    "红薯": ("地瓜",),
    "练习册": ("練習簿",),
    "结账": ("結帳",),
    "维生素": ("維他命",),
    "缓存": ("快取",),
    "编程": ("程式設計",),
    "网络": ("網路",),
    "肚子疼": ("肚子痛",),
    "芝士": ("起司", "起士"),
    "芯片": ("晶片",),
    "药店": ("藥局",),
    "菜单": ("選單",),
    "菠萝": ("鳳梨",),
    "营销": ("行銷",),
    "行驶证": ("行車執照",),
    "西红柿": ("番茄",),
    "视频": ("影片",),
    "视频通话": ("視訊通話",),
    "计划": ("計畫",),
    "计算器": ("計算機",),
    "设置": ("設定",),
    "试卷": ("考卷",),
    "读卡器": ("讀卡機",),
    "身份证": ("身分證",),
    "软件": ("軟體", "軟件"),
    "输液": ("打點滴",),
    "违章": ("違規",),
    "追尾": ("追撞",),
    "酸奶": ("優格", "優酪乳"),
    "重启": ("重新啟動",),
    "锁屏": ("鎖定螢幕",),
    "集成电路": ("積體電路",),
    "音箱": ("音響",),
    "音频": ("音訊",),
    "项目": ("專案",),
    "飞行模式": ("飛航模式",),
    "驾校": ("駕訓班",),
    "驾驶证": ("駕駛執照",),
    "高清": ("高畫質",),
    "黑客": ("駭客",),
    "默认": ("預設",),
    "鼠标": ("滑鼠",),
}

# 繁体短语 -> 简体（to_simp 用；同简体多繁体时保留先出现者）
_PHRASES_T2S = {}
for _s, _ts in _PHRASES_S2T.items():
    for _t in _ts:
        _PHRASES_T2S.setdefault(_t, _s)

# CJK 标点剥离集（查询侧）
_PUNCT = frozenset("，。、；：？！''「」『』【】〔〕（）〈〉《》—…·～｜、\u3000")

_T2S: dict[str, str] = {}
_S2T: dict[str, list[str]] = {}
for _t, _s in zip(_PAIRS[0::2], _PAIRS[1::2]):
    _T2S.setdefault(_t, _s)  # 首次出现为主（生成器已排 BMP 优先在前）
    _lst = _S2T.setdefault(_s, [])
    if _t not in _lst:
        _lst.append(_t)
# 主序重排：指定首选繁体形置顶
for _s, _p in _PRIMARY.items():
    _lst = _S2T.get(_s)
    if _lst and _p in _lst:
        _lst.remove(_p)
        _lst.insert(0, _p)


def _find_phrases(text: str, table: dict) -> list[tuple[int, int, str]]:
    """最长匹配扫描短语（不重叠），返回 [(start, end, 短语)]。"""
    found = []
    i = 0
    n = len(text)
    while i < n:
        hit = None
        for L in range(min(_MAX_PHRASE_LEN, n - i), 1, -1):
            if text[i:i + L] in table:
                hit = (i, i + L, text[i:i + L])
                break
        if hit:
            found.append(hit)
            i = hit[1]
        else:
            i += 1
    return found


def to_simp(text: str) -> str:
    """繁→简（短语感知：先替换繁体短语，其余逐字转换；无映射原样保留）。"""
    if not text:
        return text
    out = []
    last = 0
    for st, en, tp in _find_phrases(text, _PHRASES_T2S):
        out.append("".join(_T2S.get(ch, ch) for ch in text[last:st]))
        out.append(_PHRASES_T2S[tp])
        last = en
    out.append("".join(_T2S.get(ch, ch) for ch in text[last:]))
    return "".join(out)


def _strip_punct(text: str) -> str:
    """剥离 CJK 标点（查询侧用；索引侧不动）。"""
    if not text:
        return text
    return "".join(ch for ch in text if ch not in _PUNCT)


def trad_variants(text: str, cap: int = _CAP) -> list[str]:
    """简→繁组合展开：每个字展开为其全部繁体变体，笛卡尔积封顶 cap 组。

    主序优先（_PRIMARY 指定 + Unihan 顺序），截断时保留最可能的字形组合。
    """
    if not text:
        return []
    lists = []
    for ch in text:
        vs = _S2T.get(ch)
        lists.append(vs if vs else [ch])
    out: list[str] = []
    for combo in itertools.product(*lists):
        s = "".join(combo)
        if s not in out:
            out.append(s)
            if len(out) >= cap:
                break
    return out


def _phrase_forms(text: str, cap: int = 6) -> list[str]:
    """短语替换形：全短语变体笛卡尔组合（主序优先）+ 单短语替换形。

    单短语替换形保留其余简体字，供 trad_variants 补全其余字的繁体形，
    从而覆盖"短语繁体 + 其余字繁体"的文档形态（如 軟體設置）。
    """
    found = _find_phrases(text, _PHRASES_S2T)
    if not found:
        return []
    forms: list[str] = []
    for combo in itertools.product(*[_PHRASES_S2T[p] for _, _, p in found]):
        s = text
        for (st, en, _), v in zip(reversed(found), reversed(combo)):
            s = s[:st] + v + s[en:]
        if s not in forms:
            forms.append(s)
        if len(forms) >= cap:
            return forms
    for st, en, p in found:
        for v in _PHRASES_S2T[p]:
            s = text[:st] + v + text[en:]
            if s not in forms:
                forms.append(s)
                if len(forms) >= cap:
                    return forms
    return forms


def variants(text: str) -> list[str]:
    """搜索变体展开：[原文, 简体, 短语变体, 繁体组合...] 去重保序。

    与 zhconv 方案的差异（有意）：
    - zhconv 给 [原文, 简体, 繁体] 三个（繁体只一个最可能字形）；
    - 本实现：繁体侧做一简对多繁全展开 + 地区词汇短语变体（封顶），召回更高。
    """
    if not text:
        return []
    core = _strip_punct(text)
    out = [text]
    base = to_simp(core)  # 简体基准（短语感知；繁/简输入归一到同一基准）
    if base and base not in out:
        out.append(base)
    # 短语替换形（地区词汇互通）+ 其 char-level 补全展开
    for pf in _phrase_forms(base):
        if pf not in out:
            out.append(pf)
        for v in trad_variants(pf, cap=2):
            if v not in out:
                out.append(v)
    # 简体基准的 char-level 繁体展开（多繁字）
    for v in trad_variants(base, cap=_CAP):
        if v not in out:
            out.append(v)
    return out
