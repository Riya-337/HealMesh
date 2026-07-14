package executor

import (
	"encoding/json"
	"testing"
)

func TestValidatePatchAllowlist(t *testing.T) {
	tests := []struct {
		name       string
		patchBody  map[string]interface{}
		patchStr   string
		expectPass bool
	}{
		{
			name: "Allowed: Update image tag",
			patchBody: map[string]interface{}{
				"spec": map[string]interface{}{
					"template": map[string]interface{}{
						"spec": map[string]interface{}{
							"containers": []interface{}{
								map[string]interface{}{
									"name":  "my-container",
									"image": "nginx:latest",
								},
							},
						},
					},
				},
			},
			expectPass: true,
		},
		{
			name: "Allowed: Update env vars",
			patchBody: map[string]interface{}{
				"spec": map[string]interface{}{
					"template": map[string]interface{}{
						"spec": map[string]interface{}{
							"containers": []interface{}{
								map[string]interface{}{
									"name": "my-container",
									"env": []interface{}{
										map[string]interface{}{
											"name":  "LOG_LEVEL",
											"value": "DEBUG",
										},
									},
								},
							},
						},
					},
				},
			},
			expectPass: true,
		},
		{
			name: "Allowed: Update resources",
			patchBody: map[string]interface{}{
				"spec": map[string]interface{}{
					"template": map[string]interface{}{
						"spec": map[string]interface{}{
							"containers": []interface{}{
								map[string]interface{}{
									"name": "my-container",
									"resources": map[string]interface{}{
										"limits": map[string]interface{}{
											"cpu": "500m",
										},
									},
								},
							},
						},
					},
				},
			},
			expectPass: true,
		},
		{
			name: "Allowed: All allowed fields together",
			patchBody: map[string]interface{}{
				"spec": map[string]interface{}{
					"template": map[string]interface{}{
						"spec": map[string]interface{}{
							"containers": []interface{}{
								map[string]interface{}{
									"name":  "my-container",
									"image": "nginx:latest",
									"env": []interface{}{
										map[string]interface{}{
											"name":  "DEBUG",
											"value": "true",
										},
									},
									"resources": map[string]interface{}{
										"requests": map[string]interface{}{
											"memory": "128Mi",
										},
									},
								},
							},
						},
					},
				},
			},
			expectPass: true,
		},
		{
			name: "Denied: Update securityContext",
			patchBody: map[string]interface{}{
				"spec": map[string]interface{}{
					"template": map[string]interface{}{
						"spec": map[string]interface{}{
							"containers": []interface{}{
								map[string]interface{}{
									"name": "my-container",
									"securityContext": map[string]interface{}{
										"privileged": true,
									},
								},
							},
						},
					},
				},
			},
			expectPass: false,
		},
		{
			name: "Denied: Update serviceAccountName",
			patchBody: map[string]interface{}{
				"spec": map[string]interface{}{
					"template": map[string]interface{}{
						"spec": map[string]interface{}{
							"serviceAccountName": "admin",
						},
					},
				},
			},
			expectPass: false,
		},
		{
			name: "Denied: Add volumeMounts",
			patchStr: `{
				"spec": {
					"template": {
						"spec": {
							"containers": [
								{
									"name": "app",
									"volumeMounts": [{"name": "vol", "mountPath": "/mnt"}]
								}
							]
						}
					}
				}
			}`,
			expectPass: false,
		},
		{
			name: "Denied: Top-level arbitrary field",
			patchStr: `{
				"metadata": {"labels": {"foo": "bar"}},
				"spec": {
					"template": {
						"spec": {
							"containers": [{"name": "app", "image": "nginx"}]
						}
					}
				}
			}`,
			expectPass: false,
		},
		{
			name: "Denied: Multiple keys in spec",
			patchStr: `{
				"spec": {
					"replicas": 5,
					"template": {
						"spec": {
							"containers": [{"name": "app", "image": "nginx"}]
						}
					}
				}
			}`,
			expectPass: false,
		},
		{
			name: "Denied: Multiple keys in template",
			patchStr: `{
				"spec": {
					"template": {
						"metadata": {"labels": {"foo": "bar"}},
						"spec": {
							"containers": [{"name": "app", "image": "nginx"}]
						}
					}
				}
			}`,
			expectPass: false,
		},
		{
			name: "Denied: Multiple keys in pod spec",
			patchStr: `{
				"spec": {
					"template": {
						"spec": {
							"serviceAccountName": "admin",
							"containers": [{"name": "app", "image": "nginx"}]
						}
					}
				}
			}`,
			expectPass: false,
		},
		{
			name: "Denied: Containers is not an array",
			patchStr: `{
				"spec": {
					"template": {
						"spec": {
							"containers": {"name": "app", "image": "nginx"}
						}
					}
				}
			}`,
			expectPass: false,
		},
		{
			name: "Denied: Container is not an object",
			patchStr: `{
				"spec": {
					"template": {
						"spec": {
							"containers": ["nginx"]
						}
					}
				}
			}`,
			expectPass: false,
		},
		{
			name: "Denied: Missing container name",
			patchStr: `{
				"spec": {
					"template": {
						"spec": {
							"containers": [{"image": "nginx"}]
						}
					}
				}
			}`,
			expectPass: false,
		},
		{
			name: "Denied: Invalid spec type",
			patchStr: `{"spec": "not-an-object"}`,
			expectPass: false,
		},
		{
			name: "Denied: Invalid template type",
			patchStr: `{"spec": {"template": "not-an-object"}}`,
			expectPass: false,
		},
		{
			name: "Denied: Invalid pod spec type",
			patchStr: `{"spec": {"template": {"spec": "not-an-object"}}}`,
			expectPass: false,
		},
		{
			name: "Denied: spec.replicas (use SCALE instead)",
			patchStr: `{
				"spec": {
					"replicas": 5
				}
			}`,
			expectPass: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			patch := tt.patchBody
			if tt.patchStr != "" {
				if err := json.Unmarshal([]byte(tt.patchStr), &patch); err != nil {
					t.Fatalf("failed to unmarshal patch string: %v", err)
				}
			}
			err := ValidatePatchAllowlist(patch)
			if tt.expectPass {
				if err != nil {
					t.Errorf("expected pass, got error: %v", err)
				}
			} else {
				if err == nil {
					t.Errorf("expected rejection, but patch was allowed")
				}
			}
		})
	}
}
