import { Link, useLocation } from "react-router-dom";
import { preserveUiNavSearchParams } from "../utils/ui-url-args-cookie.js";

export default function UiNavLink({ to, ...props }) {
  const location = useLocation();
  return <Link to={preserveUiNavSearchParams(to, location.search)} {...props} />;
}
