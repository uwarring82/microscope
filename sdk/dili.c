#define _POSIX_C_SOURCE 200809L
#include "dili.h"
#include <libusb.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define MAX_USB_BYTES (((DILI_FULL_FRAME_BYTES + 512 + 511)/512)*512)
struct dili_camera {
    libusb_context *context;
    libusb_device_handle *device;
    int claimed, running, discard;
    unsigned width, height;
    size_t frame_bytes;
    int usb_bytes;
    uint8_t *buffer;
};
const char *dili_error(int code) {
    switch(code) {
    case 0: return "OK";
    case DILI_NOT_FOUND: return "Camera 0547:c004 not found (or USB access unavailable)";
    case DILI_MULTIPLE: return "Multiple matching cameras; connect only one";
    case DILI_UNSUPPORTED: return "Unsupported camera revision or USB interface";
    case DILI_STATE: return "Camera is not in the required acquisition state";
    case DILI_ARGUMENT: return "Invalid argument or setting outside supported range";
    case DILI_WB_REFERENCE: return "Use a brighter, unsaturated neutral reference for white balance";
    case DILI_BAD_FRAME: return "Incomplete or startup frame; no valid image returned";
    default: return libusb_error_name(code);
    }
}
static int command(dili_camera *c, uint8_t req, uint16_t value, uint16_t index) {
    int r=libusb_control_transfer(c->device,0x40,req,value,index,NULL,0,2000);
    return r<0?r:0;
}
static uint64_t millis(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC,&ts);
    return (uint64_t)ts.tv_sec*1000+ts.tv_nsec/1000000;
}
int dili_open(dili_camera **out) {
    if(!out)return DILI_ARGUMENT;
    *out=NULL;
    dili_camera *c=calloc(1,sizeof(*c));
    if(!c)return LIBUSB_ERROR_NO_MEM;
    int r=libusb_init(&c->context);
    if(r<0){free(c);return r;}
    libusb_device **list=NULL,*target=NULL;
    ssize_t n=libusb_get_device_list(c->context,&list);
    if(n<0){r=(int)n;goto done;}
    r=DILI_NOT_FOUND;
    for(ssize_t i=0;i<n;i++){
        struct libusb_device_descriptor d;
        if(libusb_get_device_descriptor(list[i],&d)<0)continue;
        if(d.idVendor!=0x0547 || d.idProduct!=0xc004)continue;
        if(target){r=DILI_MULTIPLE;goto done;}
        target=list[i];
        if(d.bcdDevice!=0xa000){r=DILI_UNSUPPORTED;goto done;}
    }
    if(!target)goto done;
    struct libusb_config_descriptor *config=NULL;
    r=libusb_get_active_config_descriptor(target,&config);
    if(r<0)goto done;
    int supported=0;
    if(config->bConfigurationValue==1 && config->bNumInterfaces==1){
        const struct libusb_interface *it=&config->interface[0];
        for(int a=0;a<it->num_altsetting;a++){
            const struct libusb_interface_descriptor *d=&it->altsetting[a];
            if(d->bInterfaceNumber==0 && d->bAlternateSetting==0 && d->bInterfaceClass==255 && d->bNumEndpoints==1){
                const struct libusb_endpoint_descriptor *e=&d->endpoint[0];
                supported=e->bEndpointAddress==0x82 && (e->bmAttributes&3)==LIBUSB_TRANSFER_TYPE_BULK && e->wMaxPacketSize==512;
                if(supported)break;
            }
        }
    }
    libusb_free_config_descriptor(config);
    if(!supported){r=DILI_UNSUPPORTED;goto done;}
    if((r=libusb_open(target,&c->device))<0)goto done;
    if((r=libusb_claim_interface(c->device,0))<0)goto done;
    c->claimed=1;
    if((r=libusb_set_interface_alt_setting(c->device,0,0))<0)goto done;
    c->width=DILI_WIDTH;c->height=DILI_HEIGHT;
    c->frame_bytes=DILI_FRAME_BYTES;c->usb_bytes=DILI_FRAME_BYTES+512;
    c->buffer=malloc(MAX_USB_BYTES);
    if(!c->buffer){r=LIBUSB_ERROR_NO_MEM;goto done;}
    *out=c;r=0;
done:
    if(list)libusb_free_device_list(list,1);
    if(r<0)dili_close(c);
    return r;
}
int dili_get_frame_size(dili_camera *c, unsigned *width, unsigned *height) {
    if(!c || !width || !height)return DILI_ARGUMENT;
    *width=c->width;*height=c->height;return 0;
}
int dili_start(dili_camera *c, unsigned exposure, unsigned gain) {
    return dili_start_mode(c,DILI_MODE_PREVIEW,exposure,gain);
}
int dili_start_mode(dili_camera *c, unsigned mode, unsigned exposure, unsigned gain) {
    if(!c || mode>DILI_MODE_FULL || exposure<1 || exposure>3000 || gain<1 || gain>70)return DILI_ARGUMENT;
    if(c->running)return DILI_STATE;
    c->width=mode==DILI_MODE_FULL?DILI_FULL_WIDTH:DILI_WIDTH;
    c->height=mode==DILI_MODE_FULL?DILI_FULL_HEIGHT:DILI_HEIGHT;
    c->frame_bytes=(size_t)c->width*c->height;
    /* Round UP: 5 MP has a 256-byte final pixel fragment after the header. */
    c->usb_bytes=(int)(((c->frame_bytes+512+511)/512)*512);
    /* Mark active before BA so failure cleanup also attempts BB. */
    c->running=1;
    int r=command(c,0xba,0,0);
    if(r<0)goto fail;
    struct timespec delay={0,300000000};
    nanosleep(&delay,NULL);
    if((r=command(c,0xb4,mode==DILI_MODE_FULL?0xc0:0xc6,0))<0)goto fail;
    if((r=command(c,0xb5,0xa0,0))<0)goto fail;
    if((r=dili_set_gain(c,gain))<0)goto fail;
    if((r=dili_set_exposure_lines(c,exposure))<0)goto fail;
    c->discard=2;
    return 0;
fail:
    dili_stop(c);return r;
}
int dili_set_exposure_lines(dili_camera *c, unsigned value) {
    if(!c || value<1 || value>3000)return DILI_ARGUMENT;
    if(!c->running)return DILI_STATE;
    int r=command(c,0xb7,(uint16_t)value,9);
    if(r==0)c->discard=2;
    return r;
}
int dili_set_gain(dili_camera *c, unsigned value) {
    if(!c || value<1 || value>70)return DILI_ARGUMENT;
    if(!c->running)return DILI_STATE;
    unsigned encoded=value<64?value:((value-63)<<8)+0x3f;
    int r=command(c,0xb7,(uint16_t)encoded,0x35);
    if(r==0)c->discard=2;
    return r;
}
int dili_read(dili_camera *c, uint8_t *pixels, size_t length, unsigned timeout_ms) {
    if(!c || !pixels || length<c->frame_bytes || timeout_ms<100 || timeout_ms>30000)return DILI_ARGUMENT;
    if(!c->running)return DILI_STATE;
    uint64_t deadline=millis()+timeout_ms;
    int r=DILI_BAD_FRAME;
    for(int attempt=0;attempt<32;attempt++){
        uint64_t now=millis();
        if(now>=deadline)break;
        int got=0;
        r=libusb_bulk_transfer(c->device,0x82,c->buffer,c->usb_bytes,&got,(unsigned)(deadline-now));
        if(r<0 || got!=c->usb_bytes){if(r==0)r=DILI_BAD_FRAME;dili_stop(c);return r;}
        if((r=command(c,0xb3,0,0))<0){dili_stop(c);return r;}
        if(c->discard>0){c->discard--;continue;}
        int invalid=0;
        for(size_t offset=512;offset<512+c->frame_bytes;offset+=512){
            int marker=1;
            for(int j=0;j<10;j++)if(c->buffer[offset+j]!=0x88){marker=0;break;}
            if(marker){invalid=1;break;}
        }
        if(invalid){r=DILI_BAD_FRAME;continue;}
        memcpy(pixels,c->buffer+512,c->frame_bytes);
        return 0;
    }
    return DILI_BAD_FRAME;
}
int dili_stop(dili_camera *c) {
    if(!c)return DILI_ARGUMENT;
    if(!c->running)return 0;
    int r=command(c,0xbb,0,0);
    c->running=0;c->discard=0;return r;
}
void dili_close(dili_camera *c) {
    if(!c)return;
    dili_stop(c);
    if(c->claimed)libusb_release_interface(c->device,0);
    if(c->device)libusb_close(c->device);
    if(c->context)libusb_exit(c->context);
    free(c->buffer);free(c);
}
