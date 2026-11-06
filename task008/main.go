package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/json"
	"fmt"
)

func main() {
	pub, priv, _ := ed25519.GenerateKey(rand.Reader)
	dest, _, _ := ed25519.GenerateKey(rand.Reader)
	from, to := Address(pub), Address(dest)
	l := NewLedger("kaspyra-dev-008", map[string]uint64{from: 1000})
	tx := Sign(l.ChainID, priv, to, 125, 0)
	if err := l.Apply(tx); err != nil {
		panic(err)
	}
	l.Height = 1
	b, _ := json.MarshalIndent(map[string]interface{}{"chain_id": l.ChainID, "height": l.Height, "state_hash": l.Hash(), "sender_balance": l.Accounts[from].Balance, "recipient_balance": l.Accounts[to].Balance, "consensus": "NOT IMPLEMENTED"}, "", "  ")
	fmt.Println(string(b))
}
