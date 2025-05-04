function hook_ssl_crypto_x509_session_verify_cert_chain(address){
  Interceptor.attach(address, {
    onEnter: function(args) { console.log("Disabling SSL certificate validation") },
    onLeave: function(retval) { console.log("Retval: " + retval); retval.replace(0x1);}
  });
}
function disable_certificate_validation(){
 var m = Process.findModuleByName("libflutter.so");
 console.log("libflutter.so loaded at ", m.base);
 var jni_onload_addr = m.enumerateExports()[0].address;
 console.log("jni_onload_address: ", jni_onload_addr);
// Adding the offset between
// ssl_crypto_x509_session_verify_cert_chain and JNI_Onload = 0xffffffffff7dcdd2
 let addr = ptr(jni_onload_addr).add(0xffffffffff7dcdd2);
 console.log("ssl_crypto_x509_session_verify_cert_chain_addr: ", addr);
 let buf = Memory.readByteArray(addr, 12);
 console.log(hexdump(buf, { offset: 0, length: 64, header: false, ansi: false}));
 hook_ssl_crypto_x509_session_verify_cert_chain(addr);

}
setTimeout(disable_certificate_validation, 1000)
