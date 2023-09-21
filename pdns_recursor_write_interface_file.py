#!/usr/bin/env python
if __name__ == "__main__":
    import PdnsRecursorInterface

    pdnsRecursorInterface = PdnsRecursorInterface.PdnsRecursorInterface()
    pdnsRecursorInterface.write_pdns_recursor_config_file()

    exit(0)
