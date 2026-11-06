package main
import("crypto/ed25519";"crypto/sha256";"encoding/hex";"encoding/json";"fmt";"testing")
func TestPayloadWireOrder(t *testing.T){
 seed:=sha256.Sum256([]byte("KASPYRA-TASK021B-TEST-ONLY-SENDER-0"));priv:=ed25519.NewKeyFromSeed(seed[:]);pub:=priv.Public().(ed25519.PublicKey);h:=sha256.Sum256(pub)
 p:=Payload{"test",hex.EncodeToString(h[:20]),"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",1,0};b,_:=json.Marshal(p)
 expected:=fmt.Sprintf(`{"chain_id":"test","from":"%s","to":"%s","amount":1,"nonce":0}`,p.From,p.To)
 if string(b)!=expected{t.Fatalf("payload mismatch: %s",b)}
 if !ed25519.Verify(pub,b,ed25519.Sign(priv,b)){t.Fatal("signature invalid")}
}
