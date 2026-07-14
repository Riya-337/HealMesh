package executor

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"testing"

	"k8s.io/client-go/rest/fake"
	"k8s.io/client-go/rest"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/kubernetes/scheme"
)

// mockRESTClient implements fake RESTClient for testing Custom Resources
func createMockRESTClient(statusCode int, responseBody []byte, err error) rest.Interface {
	return &fake.RESTClient{
		NegotiatedSerializer: scheme.Codecs.WithoutConversion(),
		GroupVersion:         schema.GroupVersion{Group: "healmesh.io", Version: "v1alpha1"},
		Client: fake.CreateHTTPClient(func(req *http.Request) (*http.Response, error) {
			if err != nil {
				return nil, err
			}
			return &http.Response{
				StatusCode: statusCode,
				Header:     http.Header{"Content-Type": []string{"application/json"}},
				Body:       io.NopCloser(bytes.NewReader(responseBody)),
			}, nil
		}),
	}
}

func TestIsActionAllowedByPolicy(t *testing.T) {
	tests := []struct {
		name       string
		action     string
		statusCode int
		response   interface{}
		want       bool
	}{
		{
			name:       "policy missing (fail closed)",
			action:     "SCALE",
			statusCode: 404,
			response:   nil,
			want:       false,
		},
		{
			name:       "empty policy list (fail closed)",
			action:     "SCALE",
			statusCode: 200,
			response: HealPolicyList{
				Items: []HealPolicy{},
			},
			want: false,
		},
		{
			name:       "policy allows action",
			action:     "SCALE",
			statusCode: 200,
			response: HealPolicyList{
				Items: []HealPolicy{
					{Spec: HealPolicySpec{AllowedActions: []string{"SCALE"}}},
				},
			},
			want: true,
		},
		{
			name:       "policy denies action",
			action:     "REDEPLOY",
			statusCode: 200,
			response: HealPolicyList{
				Items: []HealPolicy{
					{Spec: HealPolicySpec{AllowedActions: []string{"SCALE", "PATCH"}}},
				},
			},
			want: false,
		},
		{
			name:       "malformed policy",
			action:     "SCALE",
			statusCode: 200,
			response:   "invalid json",
			want:       false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var respBytes []byte
			if str, ok := tt.response.(string); ok {
				respBytes = []byte(str)
			} else if tt.response != nil {
				respBytes, _ = json.Marshal(tt.response)
			}

			client := createMockRESTClient(tt.statusCode, respBytes, nil)
			got := IsActionAllowedByPolicy(client, "default", tt.action)
			if got != tt.want {
				t.Errorf("IsActionAllowedByPolicy() = %v, want %v", got, tt.want)
			}
		})
	}
}
