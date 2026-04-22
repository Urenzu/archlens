package main

import (
	"encoding/json"
	"net/http"
)

type NotifyRequest struct {
	UserID  string `json:"user_id"`
	Channel string `json:"channel"`
	Message string `json:"message"`
}

func handleNotify(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, `{"error":"method not allowed"}`)
		return
	}
	req, err := parseNotifyRequest(r)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, `{"error":"bad request"}`)
		return
	}
	if err := validateNotifyRequest(req); err != nil {
		writeJSON(w, http.StatusUnprocessableEntity, `{"error":"validation failed"}`)
		return
	}
	dispatch(req)
	writeJSON(w, http.StatusOK, `{"queued":true}`)
}

func parseNotifyRequest(r *http.Request) (*NotifyRequest, error) {
	var req NotifyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		return nil, err
	}
	return &req, nil
}

func validateNotifyRequest(req *NotifyRequest) error {
	if req.UserID == "" {
		return &ValidationError{Field: "user_id"}
	}
	if req.Channel == "" {
		return &ValidationError{Field: "channel"}
	}
	if req.Message == "" {
		return &ValidationError{Field: "message"}
	}
	return nil
}

func dispatch(req *NotifyRequest) {
	switch req.Channel {
	case "email":
		sendEmail(req.UserID, req.Message)
	case "push":
		sendPush(req.UserID, req.Message)
	default:
		sendWebhook(req.UserID, req.Message)
	}
}

func sendEmail(userID, message string) {
	// simulate email delivery
}

func sendPush(userID, message string) {
	// simulate push notification
}

func sendWebhook(userID, message string) {
	// simulate webhook delivery
}

type ValidationError struct {
	Field string
}

func (e *ValidationError) Error() string {
	return "missing field: " + e.Field
}
