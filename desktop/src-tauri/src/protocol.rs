use serde_json::{json, Value};
use std::io::{self, BufRead};

pub const MAX_COMMAND: usize = 16_384;
pub const MAX_RESPONSE: usize = 2_097_152;
pub const MAX_PENDING: usize = 8;
pub const PUBLIC_METHODS: &[&str] = &[
    "describe",
    "models.list",
    "library.list",
    "library.for_draft",
    "library.copy_to_draft",
    "library.history",
    "library.change",
    "projects.list",
    "project.history",
    "snapshot.get",
    "source.pick",
    "source.check",
    "attachments.pick",
    "attachments.list",
    "attachments.cancel",
    "attachments.threads",
    "attachments.inspect",
    "attachments.view",
    "attachments.history",
    "attachments.search",
    "attachments.search.page",
    "attachments.scope",
    "attachments.report",
    "attachments.preview",
    "attachments.decide",
    "attachments.activity",
    "attempt.preview",
    "attempt.start",
    "attempt.cancel",
    "attempt.recover",
    "attempt.get",
    "attempt.lookup",
    "report.get",
    "report.read",
    "events.read",
    "attempt.events",
    "draft.get",
    "draft.put",
];

pub fn valid_id(value: &Value) -> bool {
    value.as_str().is_some_and(|s| {
        !s.is_empty()
            && s.len() <= 64
            && s.bytes()
                .all(|c| c.is_ascii_alphanumeric() || c == b'_' || c == b'-')
    })
}

pub fn valid_project(value: &Value) -> bool {
    // Preserve legal ledger text identifiers; capability/request IDs stay ASCII.
    value
        .as_str()
        .is_some_and(|s| !s.is_empty() && s.chars().count() <= 80)
}

// Native pick is the only frontend operation that is interpreted here. Every
// other parameter is checked again by the authoritative Python contract.
pub fn validate_request(value: &Value) -> Result<(), &'static str> {
    let object = value.as_object().ok_or("HOST_REQUEST_INVALID")?;
    if object.len() != 4
        || !["version", "id", "method", "params"]
            .iter()
            .all(|k| object.contains_key(*k))
        || value["version"].as_u64() != Some(1)
        || !valid_id(&value["id"])
        || !value["params"].is_object()
        || !value["method"]
            .as_str()
            .is_some_and(|m| PUBLIC_METHODS.contains(&m))
    {
        return Err("HOST_REQUEST_INVALID");
    }
    if serde_json::to_vec(value)
        .map_err(|_| "HOST_REQUEST_INVALID")?
        .len()
        > MAX_COMMAND
    {
        return Err("HOST_REQUEST_SIZE");
    }
    let multiple = value["method"] == "attachments.pick";
    if multiple || value["method"] == "source.pick" {
        let params = value["params"].as_object().unwrap();
        if !valid_project(&value["params"]["project_id"])
            || (multiple && (params.len() != 2 || !valid_id(&value["params"]["thread_id"])))
            || (!multiple && params.len() != 1)
        {
            return Err("HOST_PICKER_PARAMETERS");
        }
    }
    Ok(())
}

pub fn cancelled_picker(id: &Value) -> Value {
    json!({"version":1,"id":id,"ok":true,"result":null,"error":null})
}

pub fn valid_response(value: &Value) -> bool {
    value.as_object().is_some_and(|o| {
        o.len() == 5
            && ["version", "id", "ok", "result", "error"]
                .iter()
                .all(|k| o.contains_key(*k))
    }) && value["version"].as_u64() == Some(1)
        && valid_id(&value["id"])
        && match value["ok"].as_bool() {
            Some(true) => value["error"].is_null(),
            Some(false) => {
                value["result"].is_null()
                    && value["error"].as_object().is_some_and(|o| o.len() == 1)
                    && value["error"]["code"].as_str().is_some_and(|s| {
                        s.len() <= 100
                            && !s.is_empty()
                            && s.bytes()
                                .all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || c == b'_')
                    })
            }
            None => false,
        }
}

// Never let read_until allocate an unbounded response before checking its size.
pub fn bounded_line<R: BufRead>(reader: &mut R, limit: usize) -> io::Result<Option<Vec<u8>>> {
    let mut output = Vec::new();
    loop {
        let buffer = reader.fill_buf()?;
        if buffer.is_empty() {
            return if output.is_empty() {
                Ok(None)
            } else {
                Err(io::Error::new(
                    io::ErrorKind::UnexpectedEof,
                    "unterminated frame",
                ))
            };
        }
        let newline = buffer.iter().position(|b| *b == b'\n');
        let count = newline.unwrap_or(buffer.len());
        if output.len().saturating_add(count) > limit {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "frame limit"));
        }
        output.extend_from_slice(&buffer[..count]);
        reader.consume(count + usize::from(newline.is_some()));
        if newline.is_some() {
            return Ok(Some(output));
        }
    }
}

pub fn allowed_navigation(url: &tauri::Url, development: bool) -> bool {
    // Exact origins; no wildcard localhost ports or remote origins.
    (url.scheme() == "http" && url.host_str() == Some("tauri.localhost") && url.port().is_none())
        || (url.scheme() == "tauri" && url.host_str() == Some("localhost") && url.port().is_none())
        || (development
            && url.scheme() == "http"
            && url.host_str() == Some("127.0.0.1")
            && url.port() == Some(5317))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufReader, Cursor};

    #[test]
    fn ledger_project_text_is_not_an_opaque_request_id() {
        for project in [
            "Área de revisión".to_owned(),
            "x".repeat(65),
            "x".repeat(80),
            "🙂".repeat(80),
            " ".to_owned(),
            "nul\0project".to_owned(),
        ] {
            let command = json!({"version":1,"id":"opaque","method":"source.pick","params":{"project_id":project}});
            assert!(validate_request(&command).is_ok());
        }
        for project in ["".to_owned(), "x".repeat(81), "🙂".repeat(81)] {
            let command = json!({"version":1,"id":"opaque","method":"source.pick","params":{"project_id":project}});
            assert!(validate_request(&command).is_err());
        }
        assert!(!valid_id(&json!("opaque id with spaces")));
    }

    #[test]
    fn private_capture_and_forged_picker_path_never_reach_pipe() {
        let mut command = json!({"version":1,"id":"a","method":"host.source.capture","params":{"project_id":"x","path":"C:/private"}});
        assert!(validate_request(&command).is_err());
        command["method"] = json!("source.pick");
        assert!(validate_request(&command).is_err());
        command["params"] = json!({"project_id":"x"});
        assert!(validate_request(&command).is_ok());
    }

    #[test]
    fn frames_are_byte_bounded_and_require_newline() {
        let mut exact = Cursor::new(b"1234\n\n".to_vec());
        assert_eq!(bounded_line(&mut exact, 4).unwrap(), Some(b"1234".to_vec()));
        assert_eq!(bounded_line(&mut exact, 4).unwrap(), Some(vec![]));
        assert_eq!(bounded_line(&mut exact, 4).unwrap(), None);
        let mut long = BufReader::with_capacity(2, Cursor::new(b"12345\n"));
        assert!(bounded_line(&mut long, 4).is_err());
        assert!(bounded_line(&mut Cursor::new(b"1234"), 4).is_err());
    }

    #[test]
    fn multi_file_picker_accepts_only_a_project_and_thread() {
        let mut request = json!({"version":1,"id":"pick","method":"attachments.pick",
            "params":{"project_id":"Portal","thread_id":"thread-2"}});
        assert!(validate_request(&request).is_ok());
        request["params"]["paths"] = json!(["C:/unselected.txt"]);
        assert!(validate_request(&request).is_err());
        request["method"] = json!("host.attachments.capture");
        assert!(validate_request(&request).is_err());
        request["method"] = json!("attachments.pick");
        request["params"] = json!({"project_id":"Portal","thread_id":"../another-project"});
        assert!(validate_request(&request).is_err());
        request["params"] = json!({"thread_id":"valid"});
        assert!(validate_request(&request).is_err());
    }

    #[test]
    fn remote_navigation_and_development_ports_are_not_trusted() {
        for url in [
            "https://example.com",
            "http://127.0.0.1:5316",
            "http://tauri.localhost.evil",
            "http://tauri.localhost:99",
            "file:///C:/private",
        ] {
            assert!(!allowed_navigation(&url.parse().unwrap(), true), "{url}");
        }
        assert!(allowed_navigation(
            &"http://tauri.localhost".parse().unwrap(),
            false
        ));
        assert!(!allowed_navigation(
            &"http://127.0.0.1:5317".parse().unwrap(),
            false
        ));
        assert!(allowed_navigation(
            &"http://127.0.0.1:5317".parse().unwrap(),
            true
        ));
    }

    #[test]
    fn malformed_response_does_not_resolve_a_command() {
        let good =
            json!({"version":1,"id":"p1","ok":false,"result":null,"error":{"code":"DENIED"}});
        assert!(valid_response(&good));
        let mut bad = good.clone();
        bad["result"] = json!("private data");
        assert!(!valid_response(&bad));
        bad = good.clone();
        bad["error"]["code"] = json!("C:/private/file");
        assert!(!valid_response(&bad));
        bad = good.clone();
        bad["id"] = Value::Null;
        assert!(!valid_response(&bad));
    }
}
