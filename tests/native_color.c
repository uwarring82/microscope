#include "dili.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    uint8_t raw[16*16], before[sizeof(raw)], rgb[sizeof(raw)*3+8];
    double unity[3]={1,1,1}, gains[3]={7,7,7};
    for(unsigned y=0;y<16;y++)for(unsigned x=0;x<16;x++)raw[y*16+x]=!(y&1)?(!(x&1)?200:100):(!(x&1)?100:50);
    memcpy(before,raw,sizeof(raw));memset(rgb,77,sizeof(rgb));
    assert(dili_rgb8(raw,sizeof(raw),16,16,unity,rgb,sizeof(rgb)-8)==0);
    for(unsigned p=0;p<sizeof(raw);p++)assert(rgb[p*3]==200&&rgb[p*3+1]==100&&rgb[p*3+2]==50);
    assert(memcmp(raw,before,sizeof(raw))==0);
    for(unsigned p=sizeof(raw)*3;p<sizeof(rgb);p++)assert(rgb[p]==77);
    assert(dili_white_balance(raw,sizeof(raw),16,16,gains)==0);
    assert(gains[0]==0.5&&gains[1]==1&&gains[2]==2);
    assert(dili_rgb8(raw,sizeof(raw),16,16,gains,rgb,sizeof(rgb))==0);
    for(unsigned p=0;p<sizeof(raw)*3;p++)assert(rgb[p]==100);
    /* Spatial color ramps: bilinear interpolation must recover the known scene
       at every interior pixel, regardless of which channel was measured there. */
    for(unsigned y=0;y<16;y++)for(unsigned x=0;x<16;x++) {
        unsigned r=40+4*x+2*y,g=70+2*x+4*y,b=20+2*x+2*y;
        raw[y*16+x]=!(y&1)?(!(x&1)?r:g):(!(x&1)?g:b);
    }
    assert(dili_rgb8(raw,sizeof(raw),16,16,unity,rgb,sizeof(rgb))==0);
    for(unsigned y=1;y<15;y++)for(unsigned x=1;x<15;x++) {
        unsigned p=(y*16+x)*3;
        assert(rgb[p]==40+4*x+2*y&&rgb[p+1]==70+2*x+4*y&&rgb[p+2]==20+2*x+2*y);
    }
    gains[0]=8;gains[1]=8;gains[2]=8;
    memset(raw,100,sizeof(raw));assert(dili_rgb8(raw,sizeof(raw),16,16,gains,rgb,sizeof(rgb))==0);
    for(unsigned p=0;p<sizeof(raw)*3;p++)assert(rgb[p]==255);
    gains[0]=NAN;assert(dili_rgb8(raw,sizeof(raw),16,16,gains,rgb,sizeof(rgb))==DILI_ARGUMENT);
    assert(dili_rgb8(raw,sizeof(raw),15,16,unity,rgb,sizeof(rgb))==DILI_ARGUMENT);
    assert(dili_rgb8(raw,sizeof(raw)-1,16,16,unity,rgb,sizeof(rgb))==DILI_ARGUMENT);
    assert(dili_rgb8(raw,sizeof(raw),16,16,unity,rgb,1)==DILI_ARGUMENT);
    gains[0]=gains[1]=gains[2]=7;
    memset(raw,10,sizeof(raw));assert(dili_white_balance(raw,sizeof(raw),16,16,gains)==DILI_WB_REFERENCE);
    memset(raw,255,sizeof(raw));assert(dili_white_balance(raw,sizeof(raw),16,16,gains)==DILI_WB_REFERENCE);
    assert(gains[0]==7&&gains[1]==7&&gains[2]==7);
    puts("Color: RGGB channel order, spatial interpolation, edges, white balance, clipping, immutable raw and bounds passed.");
}
