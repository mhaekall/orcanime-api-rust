use aes::cipher::{KeyIvInit, BlockDecryptMut};
use aes::Aes256;
use base64::Engine;
use block_padding::Pkcs7;
use cbc::Decryptor;
use md5::{Digest, Md5};

type Aes256CbcDec = Decryptor<Aes256>;

pub fn decrypt_cryptojs_aes(encrypted_base64: &str, password: &str) -> Result<String, Box<dyn std::error::Error>> {
    // Attempt to decode the base64 wrapper JSON
    let decoded_bytes = base64::engine::general_purpose::STANDARD.decode(encrypted_base64)?;
    let decoded_str = String::from_utf8(decoded_bytes)?;
    
    let json: serde_json::Value = serde_json::from_str(&decoded_str)?;
    
    let ct_str = json["ct"].as_str().ok_or("Missing ct")?;
    let ct = base64::engine::general_purpose::STANDARD.decode(ct_str)?;
    
    let s_str = json["s"].as_str().ok_or("Missing salt")?;
    let salt = hex::decode(s_str)?;

    // EVP_BytesToKey logic (CryptoJS standard)
    let mut key_iv = Vec::new();
    let mut prev = Vec::new();
    
    while key_iv.len() < 48 {
        let mut hasher = Md5::new();
        hasher.update(&prev);
        hasher.update(password.as_bytes());
        hasher.update(&salt);
        prev = hasher.finalize().to_vec();
        key_iv.extend_from_slice(&prev);
    }
    
    let key = &key_iv[0..32];
    let iv = &key_iv[32..48];

    // Decrypt
    let dec = Aes256CbcDec::new(key.into(), iv.into());
    let mut buf = ct.clone();
    let pt = dec.decrypt_padded_mut::<Pkcs7>(&mut buf).map_err(|e| e.to_string())?;
    
    Ok(String::from_utf8(pt.to_vec())?)
}
