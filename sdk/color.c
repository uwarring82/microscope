/* Software-only processing of immutable RAW8. No USB calls. */
#include "dili.h"
#include <math.h>

static int shape(unsigned w, unsigned h, size_t size) {
    return w>=2 && h>=2 && !(w&1) && !(h&1) && w<=65534 && h<=65534 &&
           (size_t)w*h<=DILI_FULL_FRAME_BYTES && size>=(size_t)w*h;
}
static uint8_t sample8(double value) {
    if(value>=255)return 255;
    return (uint8_t)(value+0.5);
}
int dili_rgb8(const uint8_t *raw, size_t raw_size, unsigned w, unsigned h,
              const double gains[3], uint8_t *rgb, size_t rgb_size) {
    if(!raw || !rgb || !gains || !shape(w,h,raw_size) || rgb_size<(size_t)w*h*3)return DILI_ARGUMENT;
    for(int c=0;c<3;c++)if(!isfinite(gains[c]) || gains[c]<0.125 || gains[c]>8)return DILI_ARGUMENT;
    for(unsigned y=0;y<h;y++) {
        /* Reflect at image boundaries so neighboring pixels retain Bayer parity. */
        unsigned up=y?y-1:1, down=y+1<h?y+1:h-2;
        for(unsigned x=0;x<w;x++) {
            unsigned left=x?x-1:1, right=x+1<w?x+1:w-2;
            size_t p=(size_t)y*w+x;
            double r,g,b;
            unsigned horizontal=raw[(size_t)y*w+left]+raw[(size_t)y*w+right];
            unsigned vertical=raw[(size_t)up*w+x]+raw[(size_t)down*w+x];
            if((x&1)==(y&1)) {
                double diagonal=(raw[(size_t)up*w+left]+raw[(size_t)up*w+right]+
                                 raw[(size_t)down*w+left]+raw[(size_t)down*w+right])*0.25;
                g=(horizontal+vertical)*0.25;
                if(!(y&1)){r=raw[p];b=diagonal;}else{r=diagonal;b=raw[p];}
            } else {
                g=raw[p];
                if(!(y&1)){r=horizontal*0.5;b=vertical*0.5;}else{r=vertical*0.5;b=horizontal*0.5;}
            }
            rgb[3*p]=sample8(r*gains[0]);
            rgb[3*p+1]=sample8(g*gains[1]);
            rgb[3*p+2]=sample8(b*gains[2]);
        }
    }
    return 0;
}
int dili_white_balance(const uint8_t *raw, size_t raw_size, unsigned w, unsigned h, double gains[3]) {
    if(!raw || !gains || !shape(w,h,raw_size))return DILI_ARGUMENT;
    double sums[3]={0,0,0};size_t used=0,clipped=0;
    for(unsigned y=0;y<h;y+=2)for(unsigned x=0;x<w;x+=2) {
        size_t p=(size_t)y*w+x;
        unsigned r=raw[p],g1=raw[p+1],g2=raw[p+w],b=raw[p+w+1];
        /* Omit noisy shadows and saturated highlights in every channel. */
        if(r>240||g1>240||g2>240||b>240){clipped++;continue;}
        if(r+g1+g2+b<64)continue;
        sums[0]+=r;sums[1]+=(g1+g2)*0.5;sums[2]+=b;used++;
    }
    if(used<64 || clipped>(size_t)w*h/80 || sums[0]<used*8 || sums[2]<used*8)return DILI_WB_REFERENCE;
    double r=sums[1]/sums[0],b=sums[1]/sums[2];
    if(r<0.125||r>8||b<0.125||b>8)return DILI_WB_REFERENCE;
    gains[0]=r;gains[1]=1;gains[2]=b;
    return 0;
}
