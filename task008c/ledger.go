package main

import (
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
)

// Transfer is the canonical Task 008 wire format. This is a new experimental
// format, not byte-compatible with Task 007's Python JSON envelope.
type Transfer struct {
	ChainID   string `json:"chain_id"`
	From      string `json:"from"`
	To        string `json:"to"`
	Amount    uint64 `json:"amount"`
	Nonce     uint64 `json:"nonce"`
	PublicKey string `json:"public_key"`
	Signature string `json:"signature"`
}
type Payload struct {
	ChainID string `json:"chain_id"`
	From    string `json:"from"`
	To      string `json:"to"`
	Amount  uint64 `json:"amount"`
	Nonce   uint64 `json:"nonce"`
}
type Account struct {
	Balance uint64 `json:"balance"`
	Nonce   uint64 `json:"nonce"`
}
type Ledger struct {
	ChainID  string             `json:"chain_id"`
	Height   uint64             `json:"height"`
	Accounts map[string]Account `json:"accounts"`
}

func Address(pub ed25519.PublicKey) string {
	d := sha256.Sum256(pub)
	return hex.EncodeToString(d[:20])
}
func (t Transfer) payload() Payload { return Payload{t.ChainID, t.From, t.To, t.Amount, t.Nonce} }
func (t Transfer) Verify(chain string) error {
	if t.ChainID != chain || t.Amount == 0 || len(t.To) != 40 {
		return errors.New("invalid chain, amount or destination")
	}
	if _, err := hex.DecodeString(t.To); err != nil {
		return err
	}
	pub, err := hex.DecodeString(t.PublicKey)
	if err != nil || len(pub) != ed25519.PublicKeySize {
		return errors.New("invalid public key")
	}
	if Address(pub) != t.From {
		return errors.New("sender mismatch")
	}
	sig, err := hex.DecodeString(t.Signature)
	if err != nil {
		return err
	}
	b, _ := json.Marshal(t.payload())
	if !ed25519.Verify(pub, b, sig) {
		return errors.New("invalid signature")
	}
	return nil
}
func Sign(chain string, priv ed25519.PrivateKey, to string, amount, nonce uint64) Transfer {
	pub := priv.Public().(ed25519.PublicKey)
	t := Transfer{ChainID: chain, From: Address(pub), To: to, Amount: amount, Nonce: nonce, PublicKey: hex.EncodeToString(pub)}
	b, _ := json.Marshal(t.payload())
	t.Signature = hex.EncodeToString(ed25519.Sign(priv, b))
	return t
}
func (l *Ledger) Apply(t Transfer) error {
	if err := t.Verify(l.ChainID); err != nil {
		return err
	}
	sender := l.Accounts[t.From]
	if sender.Nonce != t.Nonce {
		return errors.New("nonce mismatch")
	}
	if sender.Balance < t.Amount {
		return errors.New("insufficient funds")
	}
	receiver := l.Accounts[t.To]
	if t.From != t.To && receiver.Balance > ^uint64(0)-t.Amount {
		return errors.New("recipient overflow")
	}
	if t.From != t.To {
		sender.Balance -= t.Amount
		receiver.Balance += t.Amount
		l.Accounts[t.To] = receiver
	}
	sender.Nonce++
	l.Accounts[t.From] = sender
	return nil
}
func (l *Ledger) Hash() string {
	keys := make([]string, 0, len(l.Accounts))
	for k := range l.Accounts {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	// Sorted account list makes hash independent of Go map iteration.
	type entry struct {
		Address string `json:"address"`
		Balance uint64 `json:"balance"`
		Nonce   uint64 `json:"nonce"`
	}
	rows := make([]entry, 0, len(keys))
	for _, k := range keys {
		a := l.Accounts[k]
		rows = append(rows, entry{k, a.Balance, a.Nonce})
	}
	b, _ := json.Marshal(struct {
		Chain    string  `json:"chain"`
		Height   uint64  `json:"height"`
		Accounts []entry `json:"accounts"`
	}{l.ChainID, l.Height, rows})
	d := sha256.Sum256(b)
	return fmt.Sprintf("%x", d)
}
func NewLedger(chain string, balances map[string]uint64) *Ledger {
	l := &Ledger{ChainID: chain, Accounts: map[string]Account{}}
	for k, v := range balances {
		l.Accounts[k] = Account{Balance: v}
	}
	return l
}
