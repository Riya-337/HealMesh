package executor

import (
	"fmt"
)

// ValidatePatchAllowlist ensures the patch strictly modifies only allowed fields
// (image, env, resources) inside a Deployment's container spec.
func ValidatePatchAllowlist(patch map[string]interface{}) error {
	// The patch must be at the root of a deployment object
	// The only allowed path is spec.template.spec.containers[].{image,env,resources}

	if len(patch) > 1 {
		return fmt.Errorf("only 'spec' is allowed at the root")
	}

	spec, ok := patch["spec"].(map[string]interface{})
	if !ok {
		return fmt.Errorf("missing or invalid 'spec'")
	}

	if len(spec) > 1 {
		return fmt.Errorf("only 'template' is allowed under 'spec'")
	}

	template, ok := spec["template"].(map[string]interface{})
	if !ok {
		return fmt.Errorf("missing or invalid 'template'")
	}

	if len(template) > 1 {
		return fmt.Errorf("only 'spec' is allowed under 'template'")
	}

	podSpec, ok := template["spec"].(map[string]interface{})
	if !ok {
		return fmt.Errorf("missing or invalid pod 'spec'")
	}

	if len(podSpec) > 1 {
		return fmt.Errorf("only 'containers' is allowed under pod 'spec'")
	}

	containers, ok := podSpec["containers"].([]interface{})
	if !ok {
		return fmt.Errorf("missing or invalid 'containers'")
	}

	for i, c := range containers {
		container, ok := c.(map[string]interface{})
		if !ok {
			return fmt.Errorf("invalid container at index %d", i)
		}

		for k := range container {
			if k != "name" && k != "image" && k != "env" && k != "resources" {
				return fmt.Errorf("field '%s' is not allowed in container spec", k)
			}
		}

		// Require name to identify which container to patch
		if _, ok := container["name"].(string); !ok {
			return fmt.Errorf("container name is required")
		}
	}

	return nil
}
