package executor

import (
	"testing"
)

func TestValidatePatchAllowlist(t *testing.T) {
	tests := []struct {
		name       string
		patchBody  map[string]interface{}
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
			patchBody: map[string]interface{}{
				"spec": map[string]interface{}{
					"template": map[string]interface{}{
						"spec": map[string]interface{}{
							"containers": []interface{}{
								map[string]interface{}{
									"name": "my-container",
									"volumeMounts": []interface{}{
										map[string]interface{}{
											"mountPath": "/etc/shadow",
											"name":      "shadow",
										},
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
			name: "Denied: Top-level arbitrary field",
			patchBody: map[string]interface{}{
				"metadata": map[string]interface{}{
					"labels": map[string]interface{}{
						"evil": "true",
					},
				},
			},
			expectPass: false,
		},
		{
			name: "Denied: spec.replicas (use SCALE instead)",
			patchBody: map[string]interface{}{
				"spec": map[string]interface{}{
					"replicas": 5,
				},
			},
			expectPass: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidatePatchAllowlist(tt.patchBody)
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
