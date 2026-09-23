/* Fault-injected USB transport: these tests never access physical hardware. */
#include <assert.h>
#include <stdio.h>
#include "../sdk/dili.c"
static int mode, bulk_calls, ack, stopped, released, closed, packet_count, control_error;
static unsigned packets[256][3];
static int sensor_full;
static libusb_device *devices[]={(libusb_device*)1,(libusb_device*)2,NULL};
static struct libusb_endpoint_descriptor endpoint={.bEndpointAddress=0x82,.bmAttributes=2,.wMaxPacketSize=512};
static struct libusb_interface_descriptor alt={.bInterfaceNumber=0,.bAlternateSetting=0,.bInterfaceClass=255,.bNumEndpoints=1,.endpoint=&endpoint};
static struct libusb_interface interface={.altsetting=&alt,.num_altsetting=1};
static struct libusb_config_descriptor config={.bConfigurationValue=1,.bNumInterfaces=1,.interface=&interface};
int libusb_init(libusb_context **c){*c=(libusb_context*)1;return 0;}
void libusb_exit(libusb_context *c){(void)c;}
ssize_t libusb_get_device_list(libusb_context *c,libusb_device ***list){(void)c;*list=devices;return 2;}
void libusb_free_device_list(libusb_device **l,int unref){(void)l;(void)unref;}
int libusb_get_device_descriptor(libusb_device *d,struct libusb_device_descriptor *out){
 memset(out,0,sizeof(*out));out->idVendor=(d==(libusb_device*)1 || mode==1)?0x0547:0x1234;
 out->idProduct=0xc004;out->bcdDevice=mode==2?1:0xa000;return 0;
}
int libusb_get_active_config_descriptor(libusb_device *d,struct libusb_config_descriptor **out){(void)d;*out=&config;return 0;}
void libusb_free_config_descriptor(struct libusb_config_descriptor *c){(void)c;}
int libusb_open(libusb_device *d,libusb_device_handle **h){(void)d;*h=(libusb_device_handle*)1;return 0;}
void libusb_close(libusb_device_handle *h){(void)h;closed++;}
int libusb_claim_interface(libusb_device_handle *h,int i){(void)h;assert(i==0);return 0;}
int libusb_release_interface(libusb_device_handle *h,int i){(void)h;assert(i==0);released++;return 0;}
int libusb_set_interface_alt_setting(libusb_device_handle *h,int i,int a){(void)h;assert(i==0&&a==0);return 0;}
const char *libusb_error_name(int r){(void)r;return "test USB failure";}
int libusb_control_transfer(libusb_device_handle *h,uint8_t type,uint8_t req,uint16_t value,uint16_t index,unsigned char *data,uint16_t length,unsigned timeout){
 (void)h;(void)timeout;assert(type==0x40&&data==NULL&&length==0);
 if(packet_count<256){packets[packet_count][0]=req;packets[packet_count][1]=value;packets[packet_count][2]=index;}packet_count++;
 if(req==0xb4)sensor_full=value==0xc0;
 if(req==0xb3)ack++;
 if(req==0xbb)stopped++;
 if(control_error&&req==0xb5)return LIBUSB_ERROR_PIPE;
 return 0;
}
int libusb_bulk_transfer(libusb_device_handle *h,unsigned char ep,unsigned char *data,int length,int *actual,unsigned timeout){
 (void)h;assert(ep==0x82&&length==(sensor_full?5039616:DILI_FRAME_BYTES+512)&&timeout>0);
 bulk_calls++;
 memset(data,11,length);*actual=length;
 if(sensor_full){
  /* Distinct final 256 pixels: a round-down or wrong offset loses this data. */
  for(int i=0;i<256;i++)data[512+DILI_FULL_FRAME_BYTES-256+i]=(unsigned char)i;
  memset(data+512+DILI_FULL_FRAME_BYTES,222,256); /* Transport tail is not pixels. */
 }
 if(mode==5){*actual=5039104;return 0;}
 if(mode==3){*actual=512;return 0;}
 if(mode==4){*actual=512;return LIBUSB_ERROR_TIMEOUT;}
 /* Three marker frames: two warmup discards, one rejected by packet validation. */
 if(bulk_calls<=3)memset(data+512,0x88,10);
 return 0;
}
int main(void){
 dili_camera *c=NULL;
 assert(dili_open(NULL)==DILI_ARGUMENT);
 mode=1;assert(dili_open(&c)==DILI_MULTIPLE&&c==NULL);
 mode=2;assert(dili_open(&c)==DILI_UNSUPPORTED&&c==NULL);
 mode=0;endpoint.bEndpointAddress=0x81;assert(dili_open(&c)==DILI_UNSUPPORTED&&c==NULL);endpoint.bEndpointAddress=0x82;
 assert(dili_open(&c)==0&&c);
 unsigned char *out=malloc(DILI_FRAME_BYTES);assert(out);memset(out,99,DILI_FRAME_BYTES);
 assert(dili_read(c,out,DILI_FRAME_BYTES,1000)==DILI_STATE);
 assert(dili_start(c,0,40)==DILI_ARGUMENT);
 assert(dili_start(c,500,71)==DILI_ARGUMENT);
 assert(dili_start(c,500,40)==0);
 const unsigned expected[][3]={{0xba,0,0},{0xb4,0xc6,0},{0xb5,0xa0,0},{0xb7,40,0x35},{0xb7,500,9}};
 assert(packet_count==5&&memcmp(expected,packets,sizeof(expected))==0);
 assert(dili_start(c,500,40)==DILI_STATE);
 assert(dili_read(c,out,1,1000)==DILI_ARGUMENT);
 assert(dili_read(c,out,DILI_FRAME_BYTES,1000)==0);
 assert(bulk_calls==4&&ack==4);
 for(int i=0;i<DILI_FRAME_BYTES;i++)assert(out[i]==11);
 assert(dili_set_gain(c,64)==0&&packets[packet_count-1][1]==0x013f);
 assert(dili_set_gain(c,70)==0&&packets[packet_count-1][1]==0x073f);
 assert(dili_set_gain(c,71)==DILI_ARGUMENT);
 assert(dili_set_exposure_lines(c,3000)==0&&packets[packet_count-1][1]==3000);
 assert(dili_set_exposure_lines(c,3001)==DILI_ARGUMENT);
 mode=3;memset(out,99,DILI_FRAME_BYTES);int before=stopped;
 assert(dili_read(c,out,DILI_FRAME_BYTES,1000)==DILI_BAD_FRAME&&stopped==before+1);
 for(int i=0;i<DILI_FRAME_BYTES;i++)assert(out[i]==99);
 assert(dili_read(c,out,DILI_FRAME_BYTES,1000)==DILI_STATE);
 mode=4;assert(dili_start(c,500,40)==0);
 assert(dili_read(c,out,DILI_FRAME_BYTES,1000)==LIBUSB_ERROR_TIMEOUT);
 mode=0;control_error=1;assert(dili_start(c,500,40)==LIBUSB_ERROR_PIPE);
 assert(dili_read(c,out,DILI_FRAME_BYTES,1000)==DILI_STATE);
 control_error=0;assert(dili_start(c,500,40)==0);assert(dili_read(c,out,DILI_FRAME_BYTES,1000)==0);
 assert(dili_stop(c)==0);
 assert(dili_start_mode(c,99,500,40)==DILI_ARGUMENT);
 unsigned width=0,height=0;
 assert(dili_get_frame_size(c,&width,&height)==0&&width==1280&&height==960);
 int start_packet=packet_count;
 assert(dili_start_mode(c,DILI_MODE_FULL,500,40)==0);
 assert(packets[start_packet+1][0]==0xb4&&packets[start_packet+1][1]==0xc0);
 assert(dili_get_frame_size(c,&width,&height)==0&&width==2592&&height==1944);
 assert(dili_read(c,out,DILI_FRAME_BYTES,1000)==DILI_ARGUMENT);
 unsigned char *full=malloc(DILI_FULL_FRAME_BYTES+16);assert(full);
 memset(full,77,DILI_FULL_FRAME_BYTES+16);
 assert(dili_read(c,full,DILI_FULL_FRAME_BYTES,1000)==0);
 for(int i=0;i<DILI_FULL_FRAME_BYTES-256;i++)assert(full[i]==11);
 for(int i=0;i<256;i++)assert(full[DILI_FULL_FRAME_BYTES-256+i]==i);
 for(int i=0;i<16;i++)assert(full[DILI_FULL_FRAME_BYTES+i]==77);
 mode=5;memset(full,77,DILI_FULL_FRAME_BYTES);
 assert(dili_read(c,full,DILI_FULL_FRAME_BYTES,1000)==DILI_BAD_FRAME);
 for(int i=0;i<DILI_FULL_FRAME_BYTES;i++)assert(full[i]==77);
 mode=0;
 assert(dili_start(c,500,40)==0); /* Legacy start still selects preview. */
 assert(dili_get_frame_size(c,&width,&height)==0&&width==1280&&height==960);
 assert(dili_read(c,out,DILI_FRAME_BYTES,1000)==0);
 dili_close(c);free(out);free(full);assert(released==1&&closed==1);
 puts("Native SDK: identification, protocol, frame validation, setting bounds, timeout, restart and cleanup passed.");
}
