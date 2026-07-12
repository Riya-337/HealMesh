// Package watcher provides read-only Kubernetes event watching for HealMesh.
//
// INVARIANT: This package never imports from healmesh-k8s/executor.
// It has zero write capabilities. All RBAC: get/list/watch only.
package watcher

import (
	"fmt"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/google/uuid"
)

// FailureType represents one of the five canonical Kubernetes failure types.
type FailureType string

const (
	CrashLoopBackOff      FailureType = "CrashLoopBackOff"
	OOMKilled             FailureType = "OOMKilled"
	ImagePullBackOff      FailureType = "ImagePullBackOff"
	FailedRollout         FailureType = "FailedRollout"
	ResourceQuotaExceeded FailureType = "ResourceQuotaExceeded"
)

// MaxLogLines is the hard cap on log lines sent to healmesh-core.
const MaxLogLines = 50

// MaxLineChars is the hard cap on characters per log line.
const MaxLineChars = 500

// secretPatterns are regex patterns for redacting credentials from logs.
var secretPatterns = []*regexp.Regexp{
	regexp.MustCompile(`(?i)(api[_-]?key|apikey)[\s=:"]+[A-Za-z0-9_\-]{16,}`),
	regexp.MustCompile(`(?i)(token|secret|password|passwd|pwd)[\s=:"]+[A-Za-z0-9_\-./+]{8,}`),
	regexp.MustCompile(`(?i)(bearer)\s+[A-Za-z0-9\-._~+/]+=*`),
	regexp.MustCompile(`eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+`),
	regexp.MustCompile(`(?i)(postgres|mysql|mongodb)://[^\s]+`),
	regexp.MustCompile(`AKIA[0-9A-Z]{16}`),
}

const redacted = "[REDACTED]"

// SanitizeLogLine strips credential-shaped patterns from a single log line.
func SanitizeLogLine(line string) string {
	for _, pattern := range secretPatterns {
		line = pattern.ReplaceAllString(line, redacted)
	}
	if utf8.RuneCountInString(line) > MaxLineChars {
		runes := []rune(line)
		line = string(runes[:MaxLineChars]) + "...[truncated]"
	}
	return line
}

// SanitizeLogLines applies SanitizeLogLine to all lines and caps at MaxLogLines.
func SanitizeLogLines(lines []string) []string {
	if len(lines) > MaxLogLines {
		lines = lines[len(lines)-MaxLogLines:]
	}
	sanitized := make([]string, len(lines))
	for i, line := range lines {
		sanitized[i] = SanitizeLogLine(line)
	}
	return sanitized
}

// ContainerStatus mirrors schema.models.ContainerStatus in healmesh-core.
type ContainerStatus struct {
	Name                  string  `json:"name"`
	Image                 string  `json:"image"`
	RestartCount          int32   `json:"restart_count"`
	Ready                 bool    `json:"ready"`
	LastExitCode          *int32  `json:"last_exit_code,omitempty"`
	LastTerminationReason *string `json:"last_termination_reason,omitempty"`
}

// ResourceLimits mirrors schema.models.ResourceLimits in healmesh-core.
type ResourceLimits struct {
	CPURequest    *string `json:"cpu_request,omitempty"`
	CPULimit      *string `json:"cpu_limit,omitempty"`
	MemoryRequest *string `json:"memory_request,omitempty"`
	MemoryLimit   *string `json:"memory_limit,omitempty"`
}

// IncidentPayload is the JSON payload sent to healmesh-core /incident.
// MUST match healmesh-core/schema/models.py IncidentPayload exactly.
type IncidentPayload struct {
	IncidentID        string            `json:"incident_id"`
	PodName           string            `json:"pod_name"`
	Namespace         string            `json:"namespace"`
	FailureType       FailureType       `json:"failure_type"`
	DetectedAt        time.Time         `json:"detected_at"`
	ContainerStatuses []ContainerStatus `json:"container_statuses,omitempty"`
	LogLines          []string          `json:"log_lines,omitempty"`
	ResourceLimits    *ResourceLimits   `json:"resource_limits,omitempty"`
	Image             *string           `json:"image,omitempty"`
	ImagePullPolicy   *string           `json:"image_pull_policy,omitempty"`
	DeploymentName    *string           `json:"deployment_name,omitempty"`
	DesiredReplicas   *int32            `json:"desired_replicas,omitempty"`
	ReadyReplicas     *int32            `json:"ready_replicas,omitempty"`
	QuotaResource     *string           `json:"quota_resource,omitempty"`
	QuotaLimit        *string           `json:"quota_limit,omitempty"`
	QuotaUsed         *string           `json:"quota_used,omitempty"`
}

// NewIncidentID generates a fresh UUID for an incident.
func NewIncidentID() string {
	return uuid.New().String()
}

// StringPtr returns a pointer to a string value.
func StringPtr(s string) *string { return &s }

// Int32Ptr returns a pointer to an int32 value.
func Int32Ptr(i int32) *int32 { return &i }

// ParseQuotaMessage extracts quota resource info from a Kubernetes event message.
func ParseQuotaMessage(message string) (resource, limit, used string) {
	parts := strings.Split(message, ",")
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if strings.HasPrefix(part, "limited:") {
			limited := strings.TrimPrefix(part, "limited:")
			kv := strings.SplitN(strings.TrimSpace(limited), "=", 2)
			if len(kv) == 2 {
				resource = strings.TrimSpace(kv[0])
				limit = strings.TrimSpace(kv[1])
			}
		} else if strings.HasPrefix(part, "used:") {
			usedStr := strings.TrimPrefix(part, "used:")
			kv := strings.SplitN(strings.TrimSpace(usedStr), "=", 2)
			if len(kv) == 2 {
				used = strings.TrimSpace(kv[1])
			}
		}
	}
	if resource == "" {
		maxLen := len(message)
		if maxLen > 100 {
			maxLen = 100
		}
		resource = fmt.Sprintf("quota (raw: %s)", message[:maxLen])
	}
	return resource, limit, used
}
