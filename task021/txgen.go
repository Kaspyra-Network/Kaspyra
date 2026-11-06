// Task 021B fixture generator. Deterministic TEST-ONLY keys, never for production.
package main

import (
 "crypto/ed25519"
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "fmt"
 "os"
)
type Payload struct {ChainID string `json:"chain_id"`; From string `json:"from"`; To string `json:"to"`; Amount uint64 `json:"amount"`; Nonce uint64 `json:"nonce"`}
type Transfer struct {ChainID string `json:"chain_id"`; From string `json:"from"`; To string `json:"to"`; Amount uint64 `json:"amount"`; Nonce uint64 `json:"nonce"`; PublicKey string `json:"public_key"`; Signature string `json:"signature"`}
func main(){
 if len(os.Args)!=4 {panic("usage: txgen chain sender-index nonce")}
 var idx int; var nonce uint64
 if _,err:=fmt.Sscan(os.Args[2],&idx);err!=nil || idx<0 || idx>3 {panic("invalid sender")}
 if _,err:=fmt.Sscan(os.Args[3],&nonce);err!=nil {panic("invalid nonce")}
 seed:=sha256.Sum256([]byte(fmt.Sprintf("KASPYRA-TASK021B-TEST-ONLY-SENDER-%d",idx)))
 priv:=ed25519.NewKeyFromSeed(seed[:]); pub:=priv.Public().(ed25519.PublicKey)
 hash:=sha256.Sum256(pub); from:=hex.EncodeToString(hash[:20]); to:="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
 payload:=Payload{os.Args[1],from,to,1,nonce}; bytes,_:=json.Marshal(payload)
 tx:=Transfer{payload.ChainID,payload.From,payload.To,payload.Amount,payload.Nonce,hex.EncodeToString(pub),hex.EncodeToString(ed25519.Sign(priv,bytes))}
 out,_:=json.Marshal(tx); fmt.Println(hex.EncodeToString(out))
}
