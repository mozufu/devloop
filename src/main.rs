use std::{env, fs, io::{self, Read}, path::Path};
use zutai_eval::{Value as V, Thunk, thunk::ThunkState};
use zutai_im::{Block, Pair, Value as I};
type R<T> = Result<T, Box<dyn std::error::Error>>;
fn forced(t: &Thunk) -> R<I> {
    match &*t.0.borrow() { ThunkState::Forced(v) => immediate(v), _ => Err("unforced admission value".into()) }
}
fn immediate(v: &V) -> R<I> {
    Ok(match v {
        V::Bool(true) => I::True, V::Bool(false) => I::False,
        V::Int(n) => I::Integer(*n), V::Float(n) if n.is_finite() => I::Float(*n),
        V::Text(s) => I::String(s.to_string()), V::Atom(s) => I::Atom(s.to_string()),
        V::List(xs) => I::Array(xs.iter().map(forced).collect::<R<_>>()?),
        V::Record(xs) => { let mut pairs = xs.iter().map(|(k,v)| Ok(Pair { field_name:k.to_string(), value:forced(v)? })).collect::<R<Vec<_>>>()?; pairs.sort_by(|a,b| a.field_name.cmp(&b.field_name)); I::Block(Block(pairs)) },
        // Immediate mode has no tagged payload, tuple, null, runtime type, or function.
        // Refusal is intentional: never guess a lossy JSON envelope conversion.
        _ => return Err("E_FIRST_ORDER: result cannot be represented losslessly in immediate data".into()),
    })
}
fn json(v: &I) -> R<serde_json::Value> {
    use serde_json::{Value as J, json};
    Ok(match v {
        I::True => J::Bool(true), I::False => J::Bool(false), I::Integer(n) => json!(n),
        I::Float(n) => json!(n), I::String(s) => json!(s),
        I::Atom(s) => json!({"$atom":s}),
        I::Array(xs) => J::Array(xs.iter().map(json).collect::<R<_>>()?),
        I::Block(b) => { let mut m=serde_json::Map::new(); for p in b.iter() { if m.insert(p.field_name.clone(),json(&p.value)?).is_some() { return Err(format!("E_DUPLICATE_FIELD: {}",p.field_name).into()); } } J::Object(m) }
    })
}
fn source(v: &I) -> R<String> {
    Ok(match v {
        I::True => "true".into(), I::False => "false".into(),
        I::Integer(n) => n.to_string(), I::Float(n) if n.is_finite() => serde_json::to_string(n)?,
        I::Float(_) => return Err("E_FLOAT: nonfinite immediate float".into()),
        I::String(s) => serde_json::to_string(s)?, I::Atom(s) => format!("#{s}"),
        I::Array(xs) => format!("[{}]", xs.iter().map(|x| source(x).map(|s|s+";")).collect::<R<Vec<_>>>()?.concat()),
        I::Block(b) => format!("{{{}}}", b.iter().map(|p| source(&p.value).map(|s|format!("{}={s};",p.field_name))).collect::<R<Vec<_>>>()?.concat()),
    })
}
fn main() { if let Err(e)=run() { eprintln!("{e}"); std::process::exit(1); } }
fn run() -> R<()> {
    let args:Vec<_>=env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("admit") => {
            // Package discovery walks up from the source file, so it needs a
            // path with real parent directories, not a bare relative name.
            let given = Path::new(args.get(2).ok_or("admit requires path")?);
            let canonical = fs::canonicalize(given)?;
            let path = canonical.as_path();
            let block=match path.extension().and_then(|s|s.to_str()) {
                Some("zti") => zutai_im::parse(&fs::read_to_string(path)?)?,
                Some("zt") => match immediate(&zutai_eval::eval_path(path)?)? { I::Block(b)=>b, _=>return Err("E_ROOT: requirements must be a record".into()) },
                _ => return Err("E_SOURCE: expected .zt or .zti".into())
            };
            let value = I::Block(block);
            json(&value)?;
            print!("{}",zutai_im::format_source(&source(&value)?)?);
        },
        Some("decode") | Some("format") => {
            let mut s=String::new(); io::stdin().read_to_string(&mut s)?;
            let b=zutai_im::parse(&s)?; let j=json(&I::Block(b))?;
            if args[1]=="decode" { println!("{}",j); } else { print!("{}",zutai_im::format_source(&s)?); }
        },
        _ => return Err("usage: devloop-zutai admit PATH | decode | format".into())
    }
    Ok(())
}
