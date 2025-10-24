#!/usr/bin/env python3
"""
Migration script to rename Person fields in Neo4j database.

This script:
1. Renames is_scrapped to prof_is_scrapped
2. Renames last_scrapped to prof_last_scrapped
3. Adds act_is_scrapped field (copying value from prof_is_scrapped)
4. Adds act_last_scrapped field (copying value from prof_last_scrapped)

Run this script once to migrate existing database data.
"""
import sys
import econfig
import neo4j_db


def migrate_person_fields():
    """Migrate Person node fields in the Neo4j database."""
    
    print("Starting Person field migration...")
    print("This will rename and add fields to all Person nodes in the database.")
    
    # Load environment config
    econfig.load_env()
    
    # Connect to Neo4j
    with neo4j_db.Neo4jDB() as neo_db:
        with neo_db.session() as session:
            # First, check how many Person nodes exist
            result = session.run("MATCH (p:Person) RETURN count(p) as count")
            person_count = result.single()["count"]
            print(f"Found {person_count} Person nodes to migrate.")
            
            if person_count == 0:
                print("No Person nodes found. Nothing to migrate.")
                return
            
            # Confirm before proceeding
            response = input(f"Proceed with migration of {person_count} nodes? (yes/no): ")
            if response.lower() != 'yes':
                print("Migration cancelled.")
                return
            
            print("\nStep 1: Adding new fields act_is_scrapped and act_last_scrapped...")
            # Add the new fields with values copied from old fields
            result = session.run(
                """
                MATCH (p:Person)
                WHERE p.is_scrapped IS NOT NULL
                SET p.act_is_scrapped = p.is_scrapped,
                    p.act_last_scrapped = p.last_scrapped
                RETURN count(p) as updated
                """
            )
            updated = result.single()["updated"]
            print(f"  ✓ Added act_is_scrapped and act_last_scrapped to {updated} nodes")
            
            print("\nStep 2: Renaming is_scrapped to prof_is_scrapped...")
            # Rename is_scrapped to prof_is_scrapped
            result = session.run(
                """
                MATCH (p:Person)
                WHERE p.is_scrapped IS NOT NULL
                SET p.prof_is_scrapped = p.is_scrapped
                REMOVE p.is_scrapped
                RETURN count(p) as updated
                """
            )
            updated = result.single()["updated"]
            print(f"  ✓ Renamed is_scrapped to prof_is_scrapped on {updated} nodes")
            
            print("\nStep 3: Renaming last_scrapped to prof_last_scrapped...")
            # Rename last_scrapped to prof_last_scrapped
            result = session.run(
                """
                MATCH (p:Person)
                WHERE p.last_scrapped IS NOT NULL
                SET p.prof_last_scrapped = p.last_scrapped
                REMOVE p.last_scrapped
                RETURN count(p) as updated
                """
            )
            updated = result.single()["updated"]
            print(f"  ✓ Renamed last_scrapped to prof_last_scrapped on {updated} nodes")
            
            # Verify the migration
            print("\nStep 4: Verifying migration...")
            result = session.run(
                """
                MATCH (p:Person)
                RETURN 
                    count(p) as total,
                    count(p.prof_is_scrapped) as has_prof_is_scrapped,
                    count(p.prof_last_scrapped) as has_prof_last_scrapped,
                    count(p.act_is_scrapped) as has_act_is_scrapped,
                    count(p.act_last_scrapped) as has_act_last_scrapped,
                    count(p.is_scrapped) as has_old_is_scrapped,
                    count(p.last_scrapped) as has_old_last_scrapped
                """
            )
            stats = result.single()
            
            print(f"  Total Person nodes: {stats['total']}")
            print(f"  Nodes with prof_is_scrapped: {stats['has_prof_is_scrapped']}")
            print(f"  Nodes with prof_last_scrapped: {stats['has_prof_last_scrapped']}")
            print(f"  Nodes with act_is_scrapped: {stats['has_act_is_scrapped']}")
            print(f"  Nodes with act_last_scrapped: {stats['has_act_last_scrapped']}")
            print(f"  Nodes with old is_scrapped (should be 0): {stats['has_old_is_scrapped']}")
            print(f"  Nodes with old last_scrapped (should be 0): {stats['has_old_last_scrapped']}")
            
            if stats['has_old_is_scrapped'] == 0 and stats['has_old_last_scrapped'] == 0:
                print("\n✅ Migration completed successfully!")
                print("All old fields have been renamed and new fields have been added.")
            else:
                print("\n⚠️  Warning: Some old fields still exist. Migration may be incomplete.")
                return 1
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = migrate_person_fields()
        sys.exit(exit_code or 0)
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
