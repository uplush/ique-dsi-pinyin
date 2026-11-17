/* iQue HNBC Pinyin engine, freestanding ARM9. Dictionary: see licenses/Apache-2.0-rime.txt.
 * Composition never occupies the original nickname/signature buffer.
 * No NAND writes; the original application's save UI retains that responsibility.
 */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef struct {u32 flag,pos,cap;u16 *buf;u32 cursor;} Editor;
#define EDIT ((volatile Editor*)0x02116280)
#define KBD ((volatile u32*)0x0211016c)
#ifndef DICT_ADDR
#define DICT_ADDR 0x02280000
#endif
#ifdef IME_RUNTIME
const u8 *runtime_dictionary;
#define DICT runtime_dictionary
#else
#define DICT ((const u8*)DICT_ADDR)
#endif
#define MAX_INPUT 156
#define PAGE 9
typedef struct {
    u32 magic,enabled,owner,capacity,page,count,consumed,prev_cursor,error;
    u32 offsets[512];
    char input[MAX_INPUT+1];
    u32 length;
    u8 tiles[0x3020];
} State;
State ime;
static u16 rd16(const u8*p){return p[0]|(p[1]<<8);}
static u32 rd32(const u8*p){return rd16(p)|(rd16(p+2)<<16);}
static u32 textlen(void){u32 n=0;while(n<EDIT->cap&&EDIT->buf[n])n++;return n;}
static void clear(void){ime.length=ime.page=ime.count=ime.consumed=ime.error=0;ime.input[0]=0;}
static int active(void){return EDIT->cap==10||EDIT->cap==26;}
static void sync(void){
    if(ime.magic!=0x32494d45||ime.owner!=(u32)EDIT->buf||ime.capacity!=EDIT->cap){
        ime.magic=0x32494d45;ime.owner=(u32)EDIT->buf;ime.capacity=EDIT->cap;ime.enabled=1;clear();
    }
    if(ime.length&&ime.prev_cursor!=EDIT->cursor)clear();
    ime.prev_cursor=EDIT->cursor;
}
static int compare(const char*a,const u8*b){while(*a&&*a==*b){a++;b++;}return (u8)*a-*b;}
static const u8 *lookup(const char*key){
    u32 lo=0,hi=rd32(DICT+4),n,off;const u8*p;int c;
    while(lo<hi){n=(lo+hi)>>1;off=rd32(DICT+rd32(DICT+8)+n*4);p=DICT+rd32(DICT+12)+off;
        c=compare(key,p);if(c==0){while(*p)p++;return p+1;}if(c>0)lo=n+1;else hi=n;}
    return 0;
}
static void candidates(void){
    char key[MAX_INPUT+1];u32 positions[MAX_INPUT+1],mask=0,k=0,i,n,j,req;const u8*p;
    ime.count=ime.page=ime.consumed=ime.error=0;
    for(i=0;i<ime.length;i++){
        if(ime.input[i]=='\''){if(k<32)mask|=1u<<k;positions[k]=i+1;}
        else{key[k++]=ime.input[i];positions[k]=i+1;}
    }
    /* Single-character candidates only. Consume one exact syllable prefix;
       leave any following syllables in composition until the next selection. */
    for(n=k;n>0;n--){
        key[n]=0;p=lookup(key);if(!p)continue;
        req=n>=32?mask:(mask&((1u<<n)-1));j=rd16(p);p+=2;
        for(i=0;i<j;i++){
            if(p[0]==1&&(rd32(p+1)&req)==req&&ime.count<512)ime.offsets[ime.count++]=(u32)(p-DICT);
            p+=5+2*p[0];
        }
        if(ime.count){ime.consumed=positions[n];return;}
    }
}
static int insert(const u16*word,u32 n){
    u32 len=textlen(),at=EDIT->cursor,i;
    if(at>len)at=len;
    if(n>EDIT->cap-len){ime.error=1;return 0;}
    for(i=len;i>at;i--)EDIT->buf[i+n-1]=EDIT->buf[i-1];
    for(i=0;i<n;i++)EDIT->buf[at+i]=word[i];
    len+=n;for(i=len;i<EDIT->cap;i++)EDIT->buf[i]=0;
    EDIT->pos=len<EDIT->cap?len:EDIT->cap-1;
    EDIT->cursor=at+n<EDIT->cap?at+n:EDIT->cap-1;
    EDIT->flag=1;ime.prev_cursor=EDIT->cursor;return 1;
}
static int choose(u32 slot){
    u32 idx=ime.page*PAGE+slot,i;u16 word;const u8*p;
    if(idx>=ime.count)return 0;
    p=DICT+ime.offsets[idx];if(p[0]!=1)return 0;word=rd16(p+5);
    if(!insert(&word,1))return 0;
    for(i=ime.consumed;i<ime.length;i++)ime.input[i-ime.consumed]=ime.input[i];
    ime.length-=ime.consumed;ime.input[ime.length]=0;candidates();return 1;
}
static void page(int delta){u32 last=0,n=ime.count;while(n>PAGE){last++;n-=PAGE;}
    if(delta>0){if(ime.page<last)ime.page++;}
    else if(ime.page)ime.page--;
}
static int pinyin_page(void){return active()&&KBD[12]==1;}
/* Filter the two removed hit regions, not merely their drawn arrow glyphs.
   The trampoline runs the exact original native hit test for all other keys. */
extern u32 native_hit_test(u32 keyboard,u32 x,u32 y);
u32 hit_hook(u32 keyboard,u32 x,u32 y){
    u32 hit=native_hit_test(keyboard,x,y),id;
    if(pinyin_page()){
        sync();
        if(hit&&ime.enabled){id=*(u16*)(hit+6);if(id==4||id==5)return 0;}
    }
    return hit;
}
/* Physical button navigation can dispatch a callback without a touch hit.
   Keep it inert too; native A and the bilingual English submode retain caps. */
void shift_hook(u32 keyboard,u32 maps){
    if(pinyin_page()){sync();if(ime.enabled)return;}
    ((void(*)(u32,u32))0x0203ac19)(keyboard,maps);
}
u32 pinyin_hook(void){
    u32 ch=((u32(*)(void))0x0203a6a5)(),i;u16 raw[MAX_INPUT];
    if(!active())return ch;
    sync();
    /* The Chinese tab is internal mode 1. All other tabs retain raw native
       input, including digits, grave, brackets, accents and picture symbols. */
    if(KBD[12]!=1){clear();ime.enabled=1;return ch;}
    /* Tilde/grave is the explicit bilingual switch. A pending raw sequence is
       committed only when it fits, otherwise the mode and composition survive. */
    if(ch=='`'||ch=='~'){
        if(ime.length){for(i=0;i<ime.length;i++)raw[i]=(u8)ime.input[i];if(!insert(raw,ime.length))return 0;clear();}
        ime.enabled=!ime.enabled;return 0;
    }
    if(!ime.enabled)return ch;
    if(ch==0xfc||ch==0xdc)ch='v';
    if(ch==':'&&ime.length&&ime.input[ime.length-1]=='u'){
        ime.input[ime.length-1]='v';candidates();return 0;
    }
    if(ch>='A'&&ch<='Z')ch+=32;
    if((ch>='a'&&ch<='z')||ch=='\''){
        if(ch=='\''&&(!ime.length||ime.input[ime.length-1]=='\''))return 0;
        if(ime.length<MAX_INPUT){ime.input[ime.length++]=(char)ch;ime.input[ime.length]=0;candidates();}
        else ime.error=2;
        return 0;
    }
    if(ch==8&&ime.length){ime.input[--ime.length]=0;candidates();return 0;}
    if(ch=='['){page(-1);return 0;}if(ch==']'){page(1);return 0;}
    if(ch==' '&&ime.length){if(!choose(0))ime.error=ime.error?ime.error:3;return 0;}
    /* First three native cells clear composition; each remaining cell selects
       one character. Nine visible candidates retain the native 20-pixel pitch. */
    if(ch>='1'&&ch<='3'){clear();return 0;}
    if(ch>='4'&&ch<='9'){choose(ch-'4');return 0;}
    if(ch=='0'){choose(6);return 0;}
    if(ch=='-'){choose(7);return 0;}
    if(ch=='='){choose(8);return 0;}
    if(ch==27){clear();return 0;}
    if(ime.length&&ch){ime.error=3;return 0;}
    return ch;
}
void init_hook(u16*buf,u32 cap){
    ((void(*)(u16*,u32))0x0203b1e1)(buf,cap);ime.magic=0;sync();
}
static void pixel(u32 x,u32 y,u32 color){
    u32 off=((y>>3)*32+(x>>3))*32+(y&7)*4+((x&7)>>1),shift=(x&1)*4;
    ime.tiles[off]=(ime.tiles[off]&~(15u<<shift))|(color<<shift);
}
static void box(u32 x,u32 y,u32 width,u32 height,u32 color){u32 i,j;
    for(j=y;j<y+height;j++)for(i=x;i<x+width;i++)pixel(i,j,color);
}
static void glyph(u16 cp,u32 x,u32 y,u32 width){
    u32 lo=0,hi=rd32(DICT+20),m,i,j;const u8*p;u16 row,v;
    while(lo<hi){m=(lo+hi)>>1;p=DICT+rd32(DICT+16)+m*28;v=rd16(p);
        if(v==cp){for(j=0;j<13;j++){row=rd16(p+2+j*2);for(i=0;i<width&&i<12;i++)if(row&(1u<<i))pixel(x+i,y+j,7);}return;}
        if(v<cp)lo=m+1;else hi=m;
    }
}
/* Native keys are 17 pixels high at y=3+18*row, with one-pixel rounded
 * corners and gutters. Paint complete keys, never partial labels across gaps. */
static void key(u32 x,u32 y,u32 width){
    box(x,y,width,17,3);
    box(x+1,y,width-2,17,1);box(x,y+1,width,15,1);
}
static u32 decimal(u32 n,char *out){
    u32 h=0,t=0,k=0;
    while(n>=100){h++;n-=100;}
    while(n>=10){t++;n-=10;}
    if(h)out[k++]='0'+h;
    if(h||t)out[k++]='0'+t;
    out[k++]='0'+n;return k;
}
static void page_label(void){
    char label[7];u32 pages=1,n=ime.count,k,i,x;
    while(n>PAGE){pages++;n-=PAGE;}
    k=decimal(ime.page+1,label);label[k++]='/';k+=decimal(pages,label+k);
    glyph(0x9009,93,77,12);glyph(0x5b57,105,77,12);
    x=118+(46-k*6)/2;
    for(i=0;i<k;i++)glyph(label[i],x+i*6,77,6);
}
static void chevron(u32 x,u32 right,u32 color){
    u32 i,j;
    for(i=0;i<5;i++)for(j=0;j<2;j++){
        pixel(x+(right?i:4-i)+j,79+i,color);
        pixel(x+(right?i:4-i)+j,87-i,color);
    }
}
u8* render_hook(void){
    u8*original=((u8*(*)(void))0x0203a781)();u32 i,j,n,slot,idx,x;const u8*p;
    if(!active())return original;
    sync();
    for(i=0;i<0x3020;i++)ime.tiles[i]=original[i];
    /* First tab is Chinese; native A is now mode 2. */
    if(KBD[12]!=1){clear();ime.enabled=1;return original;}
    key(69,75,19);glyph(ime.enabled?0x4e2d:0x82f1,72,77,12);
    if(ime.enabled){
        /* Match the native gutter palette. No invisible shift/caps targets. */
        box(3,39,25,17,3);box(3,57,33,17,3);
        key(9,3,59);
        n=ime.length;i=n>9?n-8:0;x=i?18:11;
        if(ime.error){
            const u16 full[]={0x5b57,0x6570,0x5df2,0x6ee1};
            const u16 long_input[]={0x62fc,0x97f3,0x8fc7,0x957f};
            const u16 no_candidate[]={0x65e0,0x5019,0x9009,0x5b57};
            const u16 *message=ime.error==1?full:(ime.error==2?long_input:no_candidate);
            for(j=0;j<4;j++)glyph(message[j],14+j*12,5,12);
        }else{
            if(!n){glyph(0x62fc,26,5,12);glyph(0x97f3,38,5,12);}
            if(i){pixel(12,15,7);pixel(14,15,7);pixel(16,15,7);}
            for(j=0;i<n;i++,j++)glyph((u8)ime.input[i],x+j*6,5,6);
        }
        for(slot=0;slot<PAGE;slot++){
            x=69+slot*20;idx=ime.page*PAGE+slot;
            key(x,3,19);
            if(idx>=ime.count){box(x+7,11,5,1,3);continue;}
            p=DICT+ime.offsets[idx];
            glyph(rd16(p+5),x+3,5,12);
        }
        key(89,75,79);
        if(n&&ime.count)page_label();
        else if(n){glyph(0x7ee7,104,77,12);glyph(0x7eed,116,77,12);glyph(0x8f93,128,77,12);glyph(0x5165,140,77,12);}
        else{glyph(0x7a7a,116,77,12);glyph(0x683c,128,77,12);}
        key(169,75,19);key(189,75,19);
        chevron(175,0,ime.page>0?7:3);
        chevron(195,1,(ime.page+1)*PAGE<ime.count?7:3);
    }
    ((void(*)(void*,u32))0x020b2ebc)(ime.tiles,0x3020);
    return ime.tiles;
}
