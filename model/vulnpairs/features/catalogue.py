"""Security-API catalogue and the role annotation added to the Joern code property graph.

Idea carried over from the crypto builder: the graph says which argument of an API call plays which role. The crypto builder marks
the key argument with a USES_AS_KEY edge. Here the same mechanism is generalised to the roles behind MegaVul's most frequent
weaknesses (memory copy and size, allocation, release, format strings, external input), plus the crypto roles.

Positions are zero-based argument positions taken from the C library, POSIX, OpenSSL, libgcrypt, GnuTLS, mbedTLS, wolfSSL and Linux
kernel crypto documentation. Nothing here was chosen from MegaVul labels; names were picked from API semantics, and the coverage
numbers (how many functions contain a catalogued call) are measured afterwards on all functions, labels ignored.

Call roles (one-hot on the CALL node): alloc, free, copy, format, input, crypto_key, crypto_weak, crypto_rand_weak, crypto_other.
Argument roles (edge type ARG -> CALL, and a one-hot on the argument node): key, size, dest, src, format, freed.
"""

import re
from typing import Dict, List, Optional, Tuple

CALL_ROLES = ["alloc", "free", "copy", "format", "input", "crypto_key", "crypto_weak", "crypto_rand_weak", "crypto_other"]
ARG_ROLES = ["key", "size", "dest", "src", "format", "freed"]
CRYPTO_CALL_ROLES = {"crypto_key", "crypto_weak", "crypto_rand_weak", "crypto_other"}
CRYPTO_ARG_ROLES = {"key"}
# New edge types appended to the 21 Joern edge types, one per argument role.
ROLE_EDGE_TYPES = {"key": "USES_AS_KEY", "size": "USES_AS_SIZE", "dest": "USES_AS_DEST", "src": "USES_AS_SRC",
                   "format": "USES_AS_FORMAT", "freed": "USES_AS_FREED"}

# name -> (call role, {zero-based position: argument role})
CATALOGUE: Dict[str, Tuple[str, Dict[int, str]]] = {}


def _add(role: str, names, args: Dict[int, str]) -> None:
    for n in names.split():
        CATALOGUE[n] = (role, args)


# ---- memory and string operations -------------------------------------------------------------------------------------------
_add("copy", "memcpy memmove bcopy wmemcpy wmemmove", {0: "dest", 1: "src", 2: "size"})
_add("copy", "memset wmemset bzero", {0: "dest", 1: "src", 2: "size"})
_add("copy", "strcpy stpcpy wcscpy strcat wcscat", {0: "dest", 1: "src"})
_add("copy", "strncpy stpncpy strncat wcsncpy wcsncat strlcpy strlcat", {0: "dest", 1: "src", 2: "size"})
_add("copy", "sprintf vsprintf", {0: "dest", 1: "format"})
_add("copy", "snprintf vsnprintf", {0: "dest", 1: "size", 2: "format"})
_add("copy", "gets", {0: "dest"})
_add("input", "fgets", {0: "dest", 1: "size"})
_add("input", "read pread recv recvfrom recvmsg", {1: "dest", 2: "size"})
_add("input", "fread", {0: "dest", 1: "size", 2: "size"})
_add("input", "scanf sscanf fscanf", {0: "format"})
_add("input", "getenv getline readlink copy_from_user", {})
_add("copy", "copy_to_user", {0: "dest", 1: "src", 2: "size"})
# ---- allocation and release -------------------------------------------------------------------------------------------------
_add("alloc", "malloc alloca kmalloc kzalloc vmalloc vzalloc g_malloc g_malloc0 av_malloc av_mallocz xmalloc OPENSSL_malloc "
              "OPENSSL_zalloc CRYPTO_malloc emalloc safe_emalloc ngx_alloc ngx_palloc ngx_pnalloc apr_palloc", {0: "size"})
_add("alloc", "calloc kcalloc g_malloc_n av_calloc xcalloc ecalloc ngx_pcalloc OPENSSL_malloc_array", {0: "size", 1: "size"})
_add("alloc", "realloc krealloc g_realloc av_realloc xrealloc erealloc", {0: "freed", 1: "size"})
_add("free", "free kfree vfree g_free av_free av_freep xfree efree OPENSSL_free CRYPTO_free ngx_free apr_pool_destroy", {0: "freed"})
_add("free", "kvfree kfree_sensitive g_slice_free", {0: "freed"})
# ---- format strings ---------------------------------------------------------------------------------------------------------
_add("format", "printf vprintf syslog err warn errx warnx", {0: "format"})
_add("format", "fprintf vfprintf dprintf", {1: "format"})
_add("format", "printk pr_err pr_warn pr_info pr_debug", {0: "format"})
# ---- cryptography: key handling ---------------------------------------------------------------------------------------------
_add("crypto_key", "EVP_EncryptInit_ex EVP_DecryptInit_ex EVP_CipherInit_ex EVP_EncryptInit_ex2 EVP_DecryptInit_ex2 EVP_CipherInit_ex2", {3: "key"})
_add("crypto_key", "EVP_EncryptInit EVP_DecryptInit EVP_CipherInit", {2: "key"})
_add("crypto_key", "AES_set_encrypt_key AES_set_decrypt_key DES_set_key DES_set_key_checked DES_set_key_unchecked Camellia_set_key", {0: "key"})
_add("crypto_key", "BF_set_key RC4_set_key", {2: "key"})
_add("crypto_key", "HMAC", {1: "key"})
_add("crypto_key", "HMAC_Init_ex HMAC_Init", {1: "key"})
_add("crypto_key", "PKCS5_PBKDF2_HMAC PKCS5_PBKDF2_HMAC_SHA1 EVP_PBE_scrypt", {0: "key"})
_add("crypto_key", "gcry_cipher_setkey gcry_mac_setkey mbedtls_cipher_setkey mbedtls_aes_setkey_enc mbedtls_aes_setkey_dec "
                   "mbedtls_md_hmac_starts wc_AesSetKey crypto_skcipher_setkey crypto_cipher_setkey crypto_aead_setkey "
                   "crypto_shash_setkey crypto_ahash_setkey crypto_blkcipher_setkey crypto_akcipher_set_priv_key", {1: "key"})
_add("crypto_key", "gnutls_cipher_init gnutls_hmac_init wc_HmacSetKey", {2: "key"})
_add("crypto_key", "crypto_secretbox_easy", {4: "key"})
_add("crypto_key", "CryptDeriveKey CryptEncrypt CryptDecrypt CryptHashData RSA_public_encrypt RSA_private_decrypt", {0: "key"})
# ---- cryptography: weak primitives and weak randomness -----------------------------------------------------------------------
_add("crypto_weak", "MD5 MD5_Init MD5Init MD4 MD2_Init SHA1 SHA1_Init DES_ecb_encrypt DES_cbc_encrypt DES_ncbc_encrypt RC4 RC2_set_key "
                    "EVP_md5 EVP_md4 EVP_sha1 EVP_des_ecb EVP_des_cbc EVP_rc4 EVP_rc2_ecb gcry_md_open", {})
_add("crypto_rand_weak", "rand srand random srandom rand_r drand48 lrand48 mrand48 erand48 nrand48 jrand48", {})
# ---- cryptography: other library calls (carry the 'crypto' signal without a key role) --------------------------------------------
_CRYPTO_PREFIX = re.compile(r"^(EVP_|AES_|DES_|RSA_|DSA_|DH_|EC_|ECDSA_|ECDH_|X509|SSL_|TLS_|DTLS_|gcry_|CRYPTO_|BN_|gnutls_|mbedtls_|"
                            r"PKCS\d*_|PEM_|RAND_|HMAC_|SHA\d*_|OPENSSL_|wc_|crypto_|NSS|PK11_|SEC_|CERT_|Crypt[A-Z]|NCrypt|BCrypt|av_aes|"
                            r"av_sha|av_md5|av_des|av_hmac|sodium_|nettle_|gpg_|gpgme_|sha\d|md5_)")

_ALLOC_WRAPPER = re.compile(r"(^|_)(m|c|re|z)alloc(_\w+)?$")
_FREE_WRAPPER = re.compile(r"(^|_)free(p)?$")


def lookup(name: str) -> Optional[Tuple[str, Dict[int, str]]]:
    """Catalogue entry for a callee name, or None. Crypto-library names without an explicit entry get role crypto_other."""
    if not name:
        return None
    hit = CATALOGUE.get(name)
    if hit:
        return hit
    if _CRYPTO_PREFIX.match(name):
        return ("crypto_other", {})
    if _ALLOC_WRAPPER.search(name):
        return ("alloc", {0: "size"})
    if _FREE_WRAPPER.search(name):
        return ("free", {0: "freed"})
    return None


def is_crypto_name(name: str) -> bool:
    entry = lookup(name)
    return entry is not None and entry[0] in CRYPTO_CALL_ROLES


def split_roles(variant: str) -> Tuple[set, set]:
    """Which call roles and argument roles a variant annotates: 'base' none, 'crypto', 'general' (non-crypto), 'full' all."""
    if variant == "base":
        return set(), set()
    if variant == "crypto":
        return set(CRYPTO_CALL_ROLES), set(CRYPTO_ARG_ROLES)
    if variant == "general":
        return set(CALL_ROLES) - CRYPTO_CALL_ROLES, set(ARG_ROLES) - CRYPTO_ARG_ROLES
    if variant == "full":
        return set(CALL_ROLES), set(ARG_ROLES)
    raise ValueError(variant)


def coverage_names() -> List[str]:
    return sorted(CATALOGUE)
