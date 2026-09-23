/* Read descriptors; optionally exercise the ISListen VA500C capture sequence.
 * Diagnostic only. No firmware writes or kernel driver installation. */
#include <libusb.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
static int command(libusb_device_handle *h, int req, int val, int index) {
    int r=libusb_control_transfer(h,0x40,req,val,index,NULL,0,2000);
    fprintf(stderr,"control 40 %02x %04x %04x: %s (%d)\n",req,val,index,r<0?libusb_error_name(r):"OK",r);
    return r;
}
int main(int argc,char **argv) {
    int r, claimed=0, started=0, rc=1;
    libusb_context *ctx=NULL; libusb_device **list=NULL; libusb_device_handle *h=NULL;
    if((r=libusb_init(&ctx))<0){fprintf(stderr,"init: %s\n",libusb_error_name(r));return 1;}
    ssize_t n=libusb_get_device_list(ctx,&list);
    fprintf(stderr,"enumerated %zd devices\n",n);
    for(ssize_t i=0;i<n;i++){
        struct libusb_device_descriptor d;
        if(libusb_get_device_descriptor(list[i],&d)<0 || d.idVendor!=0x0547 || d.idProduct!=0xc004)continue;
        printf("camera %04x:%04x bcdDevice=%04x bus=%d address=%d\n",d.idVendor,d.idProduct,d.bcdDevice,libusb_get_bus_number(list[i]),libusb_get_device_address(list[i]));
        struct libusb_config_descriptor *c=NULL;
        if(libusb_get_active_config_descriptor(list[i],&c)==0){
            printf("configuration=%d interfaces=%d\n",c->bConfigurationValue,c->bNumInterfaces);
            for(int j=0;j<c->bNumInterfaces;j++)for(int a=0;a<c->interface[j].num_altsetting;a++){
                const struct libusb_interface_descriptor *it=&c->interface[j].altsetting[a];
                printf("interface=%d alt=%d class=%d endpoints=%d\n",it->bInterfaceNumber,it->bAlternateSetting,it->bInterfaceClass,it->bNumEndpoints);
                for(int e=0;e<it->bNumEndpoints;e++)printf("endpoint=%02x attributes=%02x maxpacket=%d\n",it->endpoint[e].bEndpointAddress,it->endpoint[e].bmAttributes,it->endpoint[e].wMaxPacketSize);
            }
            libusb_free_config_descriptor(c);
        }
        r=libusb_open(list[i],&h);fprintf(stderr,"open: %s\n",libusb_error_name(r));break;
    }
    if(!h){fprintf(stderr,"target not opened\n");goto cleanup;}
    if(argc<2){rc=0;goto cleanup;}
    if((r=libusb_claim_interface(h,0))<0){fprintf(stderr,"claim: %s\n",libusb_error_name(r));goto cleanup;}
    claimed=1;
    if((r=libusb_set_interface_alt_setting(h,0,0))<0){fprintf(stderr,"alternate: %s\n",libusb_error_name(r));goto cleanup;}
    started=1;
    if(command(h,0xba,0,0)<0)goto cleanup;
    usleep(300000);
    if(command(h,0xb4,0xc6,0)<0 || command(h,0xb5,0xa0,0)<0 || command(h,0xb7,40,0x35)<0 || command(h,0xb7,500,9)<0)goto cleanup;
    const int size=1280*960+512;
    unsigned char *buf=malloc(size);
    if(!buf)goto cleanup;
    for(int frame=0;frame<8;frame++){
        int transferred=0;
        r=libusb_bulk_transfer(h,0x82,buf,size,&transferred,10000);
        fprintf(stderr,"frame %d: %s (%d) bytes=%d expected=%d\n",frame,libusb_error_name(r),r,transferred,size);
        if(transferred>0){
            char path[4096];snprintf(path,sizeof(path),"%s.%d",argv[1],frame);
            FILE *f=fopen(path,"wb");if(f){fwrite(buf,1,transferred,f);fclose(f);}else perror("output");
        }
        if(r<0 || transferred!=size)break;
        if(command(h,0xb3,0,0)<0)break;
        rc=0;
    }
    free(buf);
cleanup:
    if(started)command(h,0xbb,0,0);
    if(claimed)libusb_release_interface(h,0);
    if(h)libusb_close(h);
    if(list)libusb_free_device_list(list,1);
    libusb_exit(ctx);return rc;
}
