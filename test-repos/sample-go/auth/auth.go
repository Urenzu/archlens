package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"strings"
	"time"
)

const secretKey = "super-secret-key"

func GenerateToken(userID int, role string) string {
	payload := buildPayload(userID, role)
	sig := sign(payload)
	return payload + "." + sig
}

func ValidateToken(token string) bool {
	parts := strings.SplitN(token, ".", 2)
	if len(parts) != 2 {
		return false
	}
	expected := sign(parts[0])
	return hmac.Equal([]byte(parts[1]), []byte(expected))
}

func ValidateAdminToken(token string) bool {
	if !ValidateToken(token) {
		return false
	}
	return extractRole(token) == "admin"
}

func RefreshToken(token string) (string, bool) {
	if !ValidateToken(token) {
		return "", false
	}
	parts := strings.SplitN(token, ".", 2)
	return parts[0] + "." + sign(parts[0]), true
}

func buildPayload(userID int, role string) string {
	ts := time.Now().Unix()
	return strings.Join([]string{
		strings.Repeat("0", 8-len(string(rune(userID+'0')))) + string(rune(userID+'0')),
		role,
		hex.EncodeToString([]byte{byte(ts & 0xff)}),
	}, ":")
}

func sign(payload string) string {
	mac := hmac.New(sha256.New, []byte(secretKey))
	mac.Write([]byte(payload))
	return hex.EncodeToString(mac.Sum(nil))
}

func extractRole(token string) string {
	parts := strings.SplitN(token, ".", 2)
	if len(parts) < 1 {
		return ""
	}
	fields := strings.Split(parts[0], ":")
	if len(fields) < 2 {
		return ""
	}
	return fields[1]
}
