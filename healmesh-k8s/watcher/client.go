// Package watcher — HTTP client for sending incidents to healmesh-core.
//
// INVARIANT: This component only SENDS incidents to healmesh-core.
// It does not read back diagnoses or trigger any write operation on the cluster.
package watcher

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"

	"go.uber.org/zap"
)

// CoreClient sends incident payloads to healmesh-core.
type CoreClient struct {
	baseURL    string
	httpClient *http.Client
	logger     *zap.Logger
}

// NewCoreClient creates a new CoreClient.
func NewCoreClient(logger *zap.Logger) *CoreClient {
	coreURL := os.Getenv("CORE_URL")
	if coreURL == "" {
		coreURL = "http://healmesh-core:8000"
	}
	return &CoreClient{
		baseURL:    coreURL,
		httpClient: &http.Client{Timeout: 30 * time.Second},
		logger:     logger,
	}
}

// SendIncident POSTs an incident payload to healmesh-core /incident.
func (c *CoreClient) SendIncident(ctx context.Context, payload *IncidentPayload) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal incident payload: %w", err)
	}

	url := c.baseURL + "/incident"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to create HTTP request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		c.logger.Error("Failed to send incident to healmesh-core",
			zap.String("incident_id", payload.IncidentID),
			zap.Error(err),
		)
		return fmt.Errorf("HTTP request to healmesh-core failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("healmesh-core returned non-2xx status: %d", resp.StatusCode)
	}

	c.logger.Info("Incident sent to healmesh-core",
		zap.String("incident_id", payload.IncidentID),
		zap.Int("http_status", resp.StatusCode),
	)
	return nil
}
