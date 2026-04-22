package handlers

import (
	"encoding/json"
	"net/http"
	"os/exec"

	"github.com/sample/api/auth"
	"github.com/sample/api/db"
)

type AdminAction struct {
	Action string `json:"action"`
	Target string `json:"target"`
}

func RunAdminAction(w http.ResponseWriter, r *http.Request) {
	var action AdminAction
	if err := json.NewDecoder(r.Body).Decode(&action); err != nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}

	token := r.Header.Get("Authorization")
	if !auth.ValidateAdminToken(token) {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	result, err := dispatchAction(action)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	json.NewEncoder(w).Encode(result)
}

func dispatchAction(action AdminAction) (interface{}, error) {
	switch action.Action {
	case "purge_cache":
		return purgeCacheAction()
	case "reindex":
		return reindexAction(action.Target)
	case "run_script":
		return runScriptAction(action.Target)
	default:
		return db.GetStats(action.Action)
	}
}

func purgeCacheAction() (interface{}, error) {
	return db.PurgeCache()
}

func reindexAction(target string) (interface{}, error) {
	return db.Reindex(target)
}

// Command injection: target passed directly to shell
func runScriptAction(target string) (interface{}, error) {
	out, err := exec.Command("sh", "-c", target).Output()
	if err != nil {
		return nil, err
	}
	return string(out), nil
}
